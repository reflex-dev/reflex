"""A state manager that stores states in memory."""

import asyncio
import contextlib
import dataclasses
from collections.abc import AsyncIterator

from typing_extensions import Unpack, override

from reflex.istate.manager import StateManager, StateModificationContext
from reflex.state import BaseState, _split_substate_key


@dataclasses.dataclass
class StateManagerMemory(StateManager):
    """A state manager that stores states in memory."""

    # The mapping of client ids to states.
    states: dict[str, BaseState] = dataclasses.field(default_factory=dict)

    # The mutex ensures the dict of mutexes is updated exclusively
    _state_manager_lock: asyncio.Lock = dataclasses.field(default=asyncio.Lock())

    # The dict of mutexes for each client
    _states_locks: dict[str, asyncio.Lock] = dataclasses.field(
        default_factory=dict, init=False
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

        async with self._states_locks[token]:
            state = await self.get_state(token)
            yield state
