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
from reflex.utils import console

_EXPIRATION_ERROR_RETRY_SECONDS = 1.0


@dataclasses.dataclass
class StateManagerMemory(StateManagerExpiration, StateManager):
    """A state manager that stores states in memory."""

    _recheck_expired_locks_on_unlock: ClassVar[bool] = True

    # The mutex ensures the dict of mutexes is updated exclusively
    _state_manager_lock: asyncio.Lock = dataclasses.field(default=asyncio.Lock())

    _expiration_task: asyncio.Task | None = None

    async def _expire_states_once(self):
        """Perform one expiration pass and wait for the next check."""
        try:
            now = time.time()
            self._purge_expired_tokens(now=now)
            await self._wait_for_token_activity(
                self._prepare_expiration_wait(now=now),
            )
        except asyncio.CancelledError:
            raise
        except Exception as err:
            console.error(f"Error expiring in-memory states: {err!r}")
            await asyncio.sleep(_EXPIRATION_ERROR_RETRY_SECONDS)

    async def _expire_states(self):
        """Long running task that removes expired states from memory.

        Raises:
            asyncio.CancelledError: When the task is cancelled.
        """
        while True:
            await self._expire_states_once()

    async def _schedule_expiration_task(self):
        """Schedule the expiration task if it is not already running."""
        if self._expiration_task is None or self._expiration_task.done():
            async with self._state_manager_lock:
                if self._expiration_task is None or self._expiration_task.done():
                    self._expiration_task = asyncio.create_task(
                        self._expire_states(),
                        name="StateManagerMemory|ExpirationProcessor",
                    )
                    await asyncio.sleep(0)

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
        self._touch_token(token)
        await self._schedule_expiration_task()
        if token not in self.states:
            self.states[token] = self.state(_reflex_internal_init=True)
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
        self._touch_token(token)
        self.states[token] = state
        await self._schedule_expiration_task()

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
