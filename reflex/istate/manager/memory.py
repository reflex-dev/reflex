"""A state manager that stores states in memory."""

import asyncio
import contextlib
import dataclasses
import time
from typing import Any, Generic, cast

from typing_extensions import Unpack, override

from reflex.istate.manager import (
    StateManager,
    StateModificationContext,
    _default_token_expiration,
    _release_state_tree,
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
        self._token_expires_at[token.cache_key] = (
            time.time() + self.token_expiration,
            token,
        )
        self._ensure_expiration_task()

    def _purge_token(self, token: StateToken):
        """Remove a token from in-memory state bookkeeping.

        Args:
            token: The token to purge.
        """
        self._token_expires_at.pop(token.cache_key, None)
        self._states_locks.pop(token.lock_key, None)
        state = self.states.pop(token.cache_key, None)
        if state is not None and isinstance(token, BaseStateToken):
            _release_state_tree(state)

    def _purge_expired_tokens(self) -> float | None:
        """Purge expired in-memory state entries and return the next deadline.

        Returns:
            The next expiration deadline among unlocked tokens, if any.
        """
        now = time.time()
        next_expires_at = None
        token_expires_at = self._token_expires_at
        state_locks = self._states_locks

        for _cache_key, (expires_at, token) in list(token_expires_at.items()):
            if (
                state_lock := state_locks.get(token.lock_key)
            ) is not None and state_lock.locked():
                continue
            if expires_at <= now:
                self._purge_token(token)
                continue
            if next_expires_at is None or expires_at < next_expires_at:
                next_expires_at = expires_at

        return next_expires_at

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
    def modify_state(
        self, token: StateToken[TOKEN_TYPE], **context: Unpack[StateModificationContext]
    ) -> contextlib.AbstractAsyncContextManager[TOKEN_TYPE]:
        """Modify the state for a token while holding exclusive lock.

        Args:
            token: The token to modify the state for.
            context: The state modification context.

        Returns:
            An async context manager yielding the state for the token.
        """
        return _ModifyState(self, token)

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


class _ModifyState(Generic[TOKEN_TYPE]):
    """Async context manager behind `StateManagerMemory.modify_state`.

    Not an `asynccontextmanager`: building its async generator costs more than
    the locking it wraps, and it runs for every event.
    """

    __slots__ = ("_lock", "_manager", "_token")

    def __init__(self, manager: StateManagerMemory, token: StateToken[TOKEN_TYPE]):
        """Store the arguments of `modify_state`.

        Args:
            manager: The state manager.
            token: The token to modify the state for.
        """
        self._manager = manager
        self._token = token

    async def __aenter__(self) -> TOKEN_TYPE:
        """Take the state lock.

        Returns:
            The state for the token.
        """
        manager = self._manager
        token = self._token = manager._coerce_token(self._token)
        lock = self._lock = await manager._get_state_lock(token)
        try:
            await lock.acquire()
            try:
                state = manager._get_or_create_state(token)
                manager._track_token(token)
            except BaseException:
                lock.release()
                raise
        except BaseException:
            manager._ensure_expiration_task()
            raise
        return state

    async def __aexit__(self, *exc_info):
        """Release the state lock."""
        manager = self._manager
        try:
            # Treat modify_state like a read followed by a write so the
            # expiration window starts after the state is no longer busy.
            manager._track_token(self._token)
        finally:
            self._lock.release()
            # Re-run expiration after the lock is released in case only locked
            # tokens were being tracked when the worker last ran.
            manager._ensure_expiration_task()
