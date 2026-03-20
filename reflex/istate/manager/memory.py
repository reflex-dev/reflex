"""A state manager that stores states in memory."""

import asyncio
import contextlib
import dataclasses
import time
from collections.abc import AsyncIterator
from typing import ClassVar

from typing_extensions import Unpack, override

from reflex.istate.manager import StateManager, StateModificationContext
from reflex.istate.manager._expiration import StateManagerExpiration
from reflex.state import BaseState, _split_substate_key
from reflex.utils.tasks import ensure_task


@dataclasses.dataclass
class StateManagerMemory(StateManagerExpiration, StateManager):
    """A state manager that stores states in memory."""

    _recheck_expired_locks_on_unlock: ClassVar[bool] = True

    # The mutex ensures the dict of mutexes is updated exclusively
    _state_manager_lock: asyncio.Lock = dataclasses.field(default=asyncio.Lock())

    _expiration_task: asyncio.Task | None = dataclasses.field(default=None, init=False)

    async def _expire_states_once(self):
        """Perform one expiration pass and wait for the next check."""
        now = time.time()
        self._purge_expired_tokens(now=now)
        await self._wait_for_token_activity(
            self._prepare_expiration_wait(now=now),
        )

    def _ensure_expiration_task(self):
        """Ensure the expiration background task is running."""
        ensure_task(
            self,
            "_expiration_task",
            self._expire_states_once,
            suppress_exceptions=[Exception],
        )

    @override
    async def get_state(self, token: str) -> BaseState:
        """Get the state for a token.

        Args:
            token: The token to get the state for.

        Returns:
            The state for the token.
        """
        # Memory state manager ignores the substate suffix and always returns the top-level state.
        token = _split_substate_key(token)[0]
        if token not in self.states:
            self.states[token] = self.state(_reflex_internal_init=True)
        self._touch_token(token)
        self._ensure_expiration_task()
        return self.states[token]

    @override
    async def set_state(
        self,
        token: str,
        state: BaseState,
        **context: Unpack[StateModificationContext],
    ):
        """Set the state for a token.

        Args:
            token: The token to set the state for.
            state: The state to set.
            context: The state modification context.
        """
        token = _split_substate_key(token)[0]
        self.states[token] = state
        self._touch_token(token)
        self._ensure_expiration_task()

    @override
    @contextlib.asynccontextmanager
    async def modify_state(
        self, token: str, **context: Unpack[StateModificationContext]
    ) -> AsyncIterator[BaseState]:
        """Modify the state for a token while holding exclusive lock.

        Args:
            token: The token to modify the state for.
            context: The state modification context.

        Yields:
            The state for the token.
        """
        # Memory state manager ignores the substate suffix and always returns the top-level state.
        token = _split_substate_key(token)[0]
        if token not in self._states_locks:
            async with self._state_manager_lock:
                if token not in self._states_locks:
                    self._states_locks[token] = asyncio.Lock()

        try:
            async with self._states_locks[token]:
                yield await self.get_state(token)
        finally:
            self._notify_token_unlocked(token)

    async def close(self):
        """Cancel the in-memory expiration task."""
        async with self._state_manager_lock:
            if self._expiration_task:
                self._expiration_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._expiration_task
                self._expiration_task = None
