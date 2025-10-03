"""A state manager that stores states on disk."""

import asyncio
import contextlib
import dataclasses
import functools
from collections.abc import AsyncIterator
from hashlib import md5
from pathlib import Path

from typing_extensions import override

from reflex.istate.manager import StateManager, _default_token_expiration
from reflex.state import BaseState, _split_substate_key, _substate_key
from reflex.utils import path_ops, prerequisites


@dataclasses.dataclass
class StateManagerDisk(StateManager):
    """A state manager that stores states on disk."""

    # The mapping of client ids to states.
    states: dict[str, BaseState] = dataclasses.field(default_factory=dict)

    # The mutex ensures the dict of mutexes is updated exclusively
    _state_manager_lock: asyncio.Lock = dataclasses.field(default=asyncio.Lock())

    # The dict of mutexes for each client
    _states_locks: dict[str, asyncio.Lock] = dataclasses.field(
        default_factory=dict,
        init=False,
    )

    # The token expiration time (s).
    token_expiration: int = dataclasses.field(default_factory=_default_token_expiration)

    def __post_init_(self):
        """Create a new state manager."""
        path_ops.mkdir(self.states_directory)

        self._purge_expired_states()

    @functools.cached_property
    def states_directory(self) -> Path:
        """Get the states directory.

        Returns:
            The states directory.
        """
        return prerequisites.get_states_dir()

    def _purge_expired_states(self):
        """Purge expired states from the disk."""
        import time

        for path in path_ops.ls(self.states_directory):
            # check path is a pickle file
            if path.suffix != ".pkl":
                continue

            # load last edited field from file
            last_edited = path.stat().st_mtime

            # check if the file is older than the token expiration time
            if time.time() - last_edited > self.token_expiration:
                # remove the file
                path.unlink()

    def token_path(self, token: str) -> Path:
        """Get the path for a token.

        Args:
            token: The token to get the path for.

        Returns:
            The path for the token.
        """
        return (
            self.states_directory / f"{md5(token.encode()).hexdigest()}.pkl"
        ).absolute()

    async def load_state(self, token: str) -> BaseState | None:
        """Load a state object based on the provided token.

        Args:
            token: The token used to identify the state object.

        Returns:
            The loaded state object or None.
        """
        token_path = self.token_path(token)

        if token_path.exists():
            try:
                with token_path.open(mode="rb") as file:
                    return BaseState._deserialize(fp=file)
            except Exception:
                pass
        return None

    async def populate_substates(
        self, client_token: str, state: BaseState, root_state: BaseState
    ):
        """Populate the substates of a state object.

        Args:
            client_token: The client token.
            state: The state object to populate.
            root_state: The root state object.
        """
        for substate in state.get_substates():
            substate_token = _substate_key(client_token, substate)

            fresh_instance = await root_state.get_state(substate)
            instance = await self.load_state(substate_token)
            if instance is not None:
                # Ensure all substates exist, even if they weren't serialized previously.
                instance.substates = fresh_instance.substates
            else:
                instance = fresh_instance
            state.substates[substate.get_name()] = instance
            instance.parent_state = state

            await self.populate_substates(client_token, instance, root_state)

    @override
    async def get_state(
        self,
        token: str,
    ) -> BaseState:
        """Get the state for a token.

        Args:
            token: The token to get the state for.

        Returns:
            The state for the token.
        """
        client_token = _split_substate_key(token)[0]
        root_state = self.states.get(client_token)
        if root_state is not None:
            # Retrieved state from memory.
            return root_state

        # Deserialize root state from disk.
        root_state = await self.load_state(_substate_key(client_token, self.state))
        # Create a new root state tree with all substates instantiated.
        fresh_root_state = self.state(_reflex_internal_init=True)
        if root_state is None:
            root_state = fresh_root_state
        else:
            # Ensure all substates exist, even if they were not serialized previously.
            root_state.substates = fresh_root_state.substates
        self.states[client_token] = root_state
        await self.populate_substates(client_token, root_state, root_state)
        return root_state

    async def set_state_for_substate(self, client_token: str, substate: BaseState):
        """Set the state for a substate.

        Args:
            client_token: The client token.
            substate: The substate to set.
        """
        substate_token = _substate_key(client_token, substate)

        if substate._get_was_touched():
            substate._was_touched = False  # Reset the touched flag after serializing.
            pickle_state = substate._serialize()
            if pickle_state:
                if not self.states_directory.exists():
                    self.states_directory.mkdir(parents=True, exist_ok=True)
                self.token_path(substate_token).write_bytes(pickle_state)

        for substate_substate in substate.substates.values():
            await self.set_state_for_substate(client_token, substate_substate)

    @override
    async def set_state(self, token: str, state: BaseState):
        """Set the state for a token.

        Args:
            token: The token to set the state for.
            state: The state to set.
        """
        client_token, _ = _split_substate_key(token)
        await self.set_state_for_substate(client_token, state)

    @override
    @contextlib.asynccontextmanager
    async def modify_state(self, token: str) -> AsyncIterator[BaseState]:
        """Modify the state for a token while holding exclusive lock.

        Args:
            token: The token to modify the state for.

        Yields:
            The state for the token.
        """
        # Memory state manager ignores the substate suffix and always returns the top-level state.
        client_token, _ = _split_substate_key(token)
        if client_token not in self._states_locks:
            async with self._state_manager_lock:
                if client_token not in self._states_locks:
                    self._states_locks[client_token] = asyncio.Lock()

        async with self._states_locks[client_token]:
            state = await self.get_state(token)
            yield state
            await self.set_state(token, state)
