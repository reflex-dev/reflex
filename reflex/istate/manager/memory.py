"""A state manager that stores states in memory."""

import asyncio
import contextlib
import dataclasses
import time
from collections.abc import AsyncIterator, Iterable, Sequence
from typing import Any

from typing_extensions import Unpack, override

from reflex.istate.manager import (
    StateLease,
    StateManager,
    StateModificationContext,
    _default_token_expiration,
)
from reflex.istate.manager.token import StateToken


@dataclasses.dataclass
class StateManagerMemory(StateManager):
    """A state manager that stores states in memory."""

    # The token expiration time (s).
    token_expiration: int = dataclasses.field(default_factory=_default_token_expiration)

    # The states, by the str of their token.
    states: dict[str, Any] = dataclasses.field(default_factory=dict)

    # The keys of the states of each ident.
    _ident_keys: dict[str, set[str]] = dataclasses.field(
        default_factory=dict, init=False
    )

    # The mutex ensures the dict of mutexes is updated exclusively
    _state_manager_lock: asyncio.Lock = dataclasses.field(default_factory=asyncio.Lock)

    # The dict of mutexes for each ident
    _states_locks: dict[str, asyncio.Lock] = dataclasses.field(
        default_factory=dict,
        init=False,
    )

    # The latest expiration deadline of each ident.
    _token_expires_at: dict[str, float] = dataclasses.field(
        default_factory=dict,
        init=False,
    )

    _expiration_task: asyncio.Task | None = dataclasses.field(default=None, init=False)

    def _put(self, token: StateToken, state: Any) -> None:
        """Store a state.

        Args:
            token: The token of the state.
            state: The state.
        """
        key = str(token)
        self.states[key] = state
        self._ident_keys.setdefault(token.ident, set()).add(key)

    def _track_idents(self, tokens: Iterable[StateToken]):
        """Refresh the expiration deadline of the idents of some tokens.

        Args:
            tokens: The tokens in use.
        """
        expires_at = time.time() + self.token_expiration
        for ident in {token.ident for token in tokens}:
            self._token_expires_at[ident] = expires_at
        self._ensure_expiration_task()

    def _purge_ident(self, ident: str):
        """Remove the states of an ident.

        Args:
            ident: The ident to purge.
        """
        self._token_expires_at.pop(ident, None)
        self._states_locks.pop(ident, None)
        for key in self._ident_keys.pop(ident, ()):
            self.states.pop(key, None)

    def _purge_expired_tokens(self) -> float | None:
        """Purge expired in-memory state entries and return the next deadline.

        Returns:
            The next expiration deadline among unlocked idents, if any.
        """
        now = time.time()
        next_expires_at = None
        state_locks = self._states_locks

        for ident, expires_at in list(self._token_expires_at.items()):
            if (
                state_lock := state_locks.get(ident)
            ) is not None and state_lock.locked():
                continue
            if expires_at <= now:
                self._purge_ident(ident)
                continue
            if next_expires_at is None or expires_at < next_expires_at:
                next_expires_at = expires_at

        return next_expires_at

    async def _get_state_lock(self, ident: str) -> asyncio.Lock:
        """Get or create the lock for an ident.

        Args:
            ident: The ident to lock.

        Returns:
            The lock protecting the ident's states.
        """
        state_lock = self._states_locks.get(ident)
        if state_lock is None:
            async with self._state_manager_lock:
                state_lock = self._states_locks.get(ident)
                if state_lock is None:
                    state_lock = self._states_locks[ident] = asyncio.Lock()
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
    async def load_states(
        self, tokens: Sequence[StateToken], *, create: bool = True
    ) -> list[Any]:
        """Load the stored states for some tokens.

        A created state is stored right away, so every context shares it.

        Args:
            tokens: The tokens of the states to load.
            create: Whether to create the states that are not stored.

        Returns:
            The state for each token, in order.
        """
        states = []
        for token in tokens:
            if (state := self.states.get(str(token))) is None and create:
                state = token.new_instance()
                self._put(token, state)
            states.append(state)
        self._track_idents(tokens)
        return states

    @override
    async def store_states(
        self,
        states: Sequence[tuple[StateToken, Any]],
        lease: StateLease | None,
        **context: Unpack[StateModificationContext],
    ) -> None:
        """Store states.

        Args:
            states: The tokens and states to store.
            lease: The lease of the lock held on the states' ident, if any.
            context: The state modification context.
        """
        for token, state in states:
            self._put(token, state)
        self._track_idents(token for token, _ in states)

    @override
    @contextlib.asynccontextmanager
    async def lock(
        self, token: StateToken, **context: Unpack[StateModificationContext]
    ) -> AsyncIterator[StateLease]:
        """Hold the exclusive lock on a token's ident.

        Args:
            token: The token to lock.
            context: The state modification context.

        Yields:
            The lease of the lock.
        """
        state_lock = await self._get_state_lock(token.ident)
        try:
            async with state_lock:
                yield StateLease(ident=token.ident)
                # The expiration window starts once the states are no longer busy.
                self._track_idents((token,))
        finally:
            # Re-run expiration after the lock is released in case only locked
            # idents were being tracked when the worker last ran.
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
            for ident, lock in tuple(self._states_locks.items()):
                if not lock.locked():
                    self._states_locks.pop(ident)
