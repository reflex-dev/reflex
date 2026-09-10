"""A state manager that stores states in memory."""

import asyncio
import contextlib
import dataclasses
import heapq
import time
from collections.abc import AsyncIterator
from typing import Any, cast

from typing_extensions import Unpack, override

from reflex.istate.manager import (
    StateManager,
    StateModificationContext,
    _default_token_expiration,
)
from reflex.istate.manager.token import TOKEN_TYPE, BaseStateToken, StateToken


@dataclasses.dataclass
class StateManagerMemory(StateManager):
    """A state manager that stores states in memory."""

    # The token expiration time (s).
    token_expiration: int = dataclasses.field(default_factory=_default_token_expiration)

    # The mapping of client ids to states.
    states: dict[str, Any] = dataclasses.field(default_factory=dict)

    # The mutex ensures the dict of mutexes is updated exclusively
    _state_manager_lock: asyncio.Lock = dataclasses.field(default_factory=asyncio.Lock)

    # The dict of mutexes for each client
    _states_locks: dict[str, asyncio.Lock] = dataclasses.field(
        default_factory=dict,
        init=False,
    )

    # The latest expiration deadline and token for each cache key.
    _token_expires_at: dict[str, tuple[float, StateToken]] = dataclasses.field(
        default_factory=dict,
        init=False,
    )

    # One heap entry per tracked token, updated in place on refresh.
    _expiration_heap: list[tuple[float, str]] = dataclasses.field(
        default_factory=list,
        init=False,
    )
    _expiration_indices: dict[str, int] = dataclasses.field(
        default_factory=dict,
        init=False,
    )

    _expiration_task: asyncio.Task | None = dataclasses.field(default=None, init=False)

    def _get_or_create_state(self, token: StateToken[TOKEN_TYPE]) -> TOKEN_TYPE:
        """Get an existing state or create a fresh one for a token.

        Args:
            token: The normalized client token.

        Returns:
            The state for the token.
        """
        key = token.cache_key
        if key not in self.states:
            if isinstance(token, BaseStateToken):
                self.states[key] = token.cls.get_root_state()(
                    _reflex_internal_init=True
                )
            else:
                self.states[key] = token.cls()
        return cast(TOKEN_TYPE, self.states[key])

    def _track_token(self, token: StateToken):
        """Refresh the expiration deadline for an active token."""
        key = token.cache_key
        expires_at = time.time() + self.token_expiration
        self._token_expires_at[key] = (expires_at, token)
        self._queue_expiration(key, expires_at)
        self._ensure_expiration_task()

    def _queue_expiration(self, key: str, expires_at: float):
        """Insert or update a token's deadline without retaining obsolete entries.

        Args:
            key: The token's cache key.
            expires_at: The expiration deadline.
        """
        index = self._expiration_indices.get(key)
        if index is None:
            index = len(self._expiration_heap)
            self._expiration_heap.append((expires_at, key))
        else:
            self._expiration_heap[index] = (expires_at, key)
        self._sift_expiration(index)

    def _remove_expiration(self, key: str):
        """Remove a token's deadline from the index.

        Args:
            key: The token's cache key.
        """
        index = self._expiration_indices.pop(key, None)
        if index is None:
            return
        last = self._expiration_heap.pop()
        if index < len(self._expiration_heap):
            self._expiration_heap[index] = last
            self._sift_expiration(index)

    def _sift_expiration(self, index: int):
        """Restore heap order and positions after a deadline changes.

        Args:
            index: The changed entry's position.
        """
        heap = self._expiration_heap
        indices = self._expiration_indices
        entry = heap[index]
        while index > 0:
            parent = (index - 1) // 2
            if heap[parent] <= entry:
                break
            heap[index] = heap[parent]
            indices[heap[index][1]] = index
            index = parent
        while (child := 2 * index + 1) < len(heap):
            if child + 1 < len(heap) and heap[child + 1] < heap[child]:
                child += 1
            if entry <= heap[child]:
                break
            heap[index] = heap[child]
            indices[heap[index][1]] = index
            index = child
        heap[index] = entry
        indices[entry[1]] = index

    def _purge_token(self, token: StateToken):
        """Remove a token from in-memory state bookkeeping.

        Args:
            token: The token to purge.
        """
        key = token.cache_key
        self._remove_expiration(key)
        self._token_expires_at.pop(key, None)
        self._states_locks.pop(token.lock_key, None)
        self.states.pop(key, None)

    def _purge_expired_tokens(self) -> float | None:
        """Purge expired in-memory state entries and return the next deadline.

        Returns:
            The next expiration deadline among unlocked tokens, if any.
        """
        now = time.time()
        count = len(self._expiration_heap)
        if not count:
            return None
        # Bound heap repairs by the cost of a linear scan when many deadlines
        # coincide or held locks must be skipped.
        heap_budget = count // count.bit_length()
        locked: list[tuple[float, str]] = []
        try:
            while self._expiration_heap:
                if not heap_budget:
                    # The scan rebuilds all remaining entries, including held
                    # tokens already removed from the heap by this pass.
                    locked.clear()
                    return self._purge_expired_tokens_scan(now)
                expires_at, key = self._expiration_heap[0]
                token = self._token_expires_at[key][1]
                if (
                    state_lock := self._states_locks.get(token.lock_key)
                ) is not None and state_lock.locked():
                    self._remove_expiration(key)
                    locked.append((expires_at, key))
                    heap_budget -= 1
                    continue
                if expires_at > now:
                    return expires_at
                self._purge_token(token)
                heap_budget -= 1
            return None
        finally:
            # Retain held tokens for the worker restarted after lock release.
            for expires_at, key in locked:
                self._queue_expiration(key, expires_at)

    def _purge_expired_tokens_scan(self, now: float) -> float | None:
        """Expire a batch with a linear scan and rebuild the deadline index.

        Args:
            now: The current time.

        Returns:
            The next expiration deadline among unlocked tokens, if any.
        """
        self._expiration_heap.clear()
        self._expiration_indices.clear()
        next_expires_at = None
        try:
            for expires_at, token in list(self._token_expires_at.values()):
                if (
                    state_lock := self._states_locks.get(token.lock_key)
                ) is not None and state_lock.locked():
                    continue
                if expires_at <= now:
                    self._purge_token(token)
                elif next_expires_at is None or expires_at < next_expires_at:
                    next_expires_at = expires_at
            return next_expires_at
        finally:
            self._expiration_heap.extend(
                (expires_at, key)
                for key, (expires_at, _) in self._token_expires_at.items()
            )
            heapq.heapify(self._expiration_heap)
            self._expiration_indices.update(
                (key, index) for index, (_, key) in enumerate(self._expiration_heap)
            )

    async def _get_state_lock(self, token: StateToken) -> asyncio.Lock:
        """Get or create the lock for a token.

        Args:
            token: The normalized client token.

        Returns:
            The lock protecting the token's state.
        """
        state_lock = self._states_locks.get(token.lock_key)
        if state_lock is None:
            async with self._state_manager_lock:
                state_lock = self._states_locks.get(token.lock_key)
                if state_lock is None:
                    state_lock = self._states_locks[token.lock_key] = asyncio.Lock()
        return state_lock

    async def _expire_states(self):
        """Purge expired states until there are no unlocked deadlines left."""
        try:
            while True:
                if (next_expires_at := self._purge_expired_tokens()) is None:
                    return
                await asyncio.sleep(max(0.0, next_expires_at - time.time()))
        finally:
            if self._expiration_task is asyncio.current_task():
                self._expiration_task = None

    def _ensure_expiration_task(self):
        """Ensure the expiration background task is running."""
        if self._expiration_task is None or self._expiration_task.done():
            asyncio.get_running_loop()  # Ensure we're in an event loop.
            self._expiration_task = asyncio.create_task(
                self._expire_states(),
                name="StateManagerMemory|Expiration",
            )

    @override
    async def get_state(self, token: StateToken[TOKEN_TYPE]) -> TOKEN_TYPE:
        """Get the state for a token.

        Args:
            token: The token to get the state for.

        Returns:
            The state for the token.
        """
        token = self._coerce_token(token)
        state = self._get_or_create_state(token)
        self._track_token(token)
        return state

    @override
    async def set_state(
        self,
        token: StateToken[TOKEN_TYPE],
        state: TOKEN_TYPE,
        **context: Unpack[StateModificationContext],
    ):
        """Set the state for a token.

        Args:
            token: The token to set the state for.
            state: The state to set.
            context: The state modification context.
        """
        token = self._coerce_token(token)
        self.states[token.cache_key] = state
        self._track_token(token)

    @override
    @contextlib.asynccontextmanager
    async def modify_state(
        self, token: StateToken[TOKEN_TYPE], **context: Unpack[StateModificationContext]
    ) -> AsyncIterator[TOKEN_TYPE]:
        """Modify the state for a token while holding exclusive lock.

        Args:
            token: The token to modify the state for.
            context: The state modification context.

        Yields:
            The state for the token.
        """
        token = self._coerce_token(token)
        state_lock = await self._get_state_lock(token)

        try:
            async with state_lock:
                state = self._get_or_create_state(token)
                self._track_token(token)
                try:
                    yield state
                finally:
                    # Treat modify_state like a read followed by a write so the
                    # expiration window starts after the state is no longer busy.
                    self._track_token(token)
        finally:
            # Re-run expiration after the lock is released in case only locked
            # tokens were being tracked when the worker last ran.
            self._ensure_expiration_task()

    async def close(self):
        """Cancel the in-memory expiration task."""
        async with self._state_manager_lock:
            if self._expiration_task:
                self._expiration_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._expiration_task
                self._expiration_task = None
            # Dump unlocked locks.
            for token, lock in tuple(self._states_locks.items()):
                if not lock.locked():
                    self._states_locks.pop(token)
