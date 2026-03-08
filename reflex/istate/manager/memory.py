"""A state manager that stores states in memory."""

import asyncio
import contextlib
import dataclasses
from collections.abc import AsyncIterator
from typing import Any, cast

from typing_extensions import Unpack, override

from reflex.istate.manager import StateManager, StateModificationContext
from reflex.istate.manager.token import TOKEN_TYPE, BaseStateToken, StateToken


@dataclasses.dataclass
class StateManagerMemory(StateManager):
    """A state manager that stores states in memory."""

    # The mapping of client ids to states.
    states: dict[str, Any] = dataclasses.field(default_factory=dict)

    # The mutex ensures the dict of mutexes is updated exclusively
    _state_manager_lock: asyncio.Lock = dataclasses.field(default=asyncio.Lock())

    # The dict of mutexes for each client
    _states_locks: dict[str, asyncio.Lock] = dataclasses.field(
        default_factory=dict, init=False
    )

    @override
    async def get_state(self, token: StateToken[TOKEN_TYPE]) -> TOKEN_TYPE:
        """Get the state for a token.

        Args:
            token: The token to get the state for.

        Returns:
            The state for the token.
        """
        key = token.ident if isinstance(token, BaseStateToken) else str(token)
        if key not in self.states:
            if isinstance(token, BaseStateToken):
                self.states[key] = token.cls.get_root_state()(
                    _reflex_internal_init=True
                )
            else:
                self.states[key] = token.cls()
        return cast(TOKEN_TYPE, self.states[key])

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
        key = token.ident if isinstance(token, BaseStateToken) else str(token)
        self.states[key] = state

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
        if token.ident not in self._states_locks:
            async with self._state_manager_lock:
                if token.ident not in self._states_locks:
                    self._states_locks[token.ident] = asyncio.Lock()

        async with self._states_locks[token.ident]:
            state = await self.get_state(token)
            yield state
            await self.set_state(token, state, **context)
