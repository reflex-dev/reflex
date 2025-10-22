"""State manager for managing client states."""

import contextlib
import dataclasses
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TypedDict

from typing_extensions import ReadOnly, Unpack

from reflex import constants
from reflex.config import get_config
from reflex.event import Event
from reflex.state import BaseState
from reflex.utils import console, prerequisites
from reflex.utils.exceptions import InvalidStateManagerModeError


class StateModificationContext(TypedDict, total=False):
    """The context for modifying state."""

    event: ReadOnly[Event]


EmptyContext = StateModificationContext()


@dataclasses.dataclass
class StateManager(ABC):
    """A class to manage many client states."""

    # The state class to use.
    state: type[BaseState]

    @classmethod
    def create(cls, state: type[BaseState]):
        """Create a new state manager.

        Args:
            state: The state class to use.

        Raises:
            InvalidStateManagerModeError: If the state manager mode is invalid.

        Returns:
            The state manager (either disk, memory or redis).
        """
        config = get_config()
        if prerequisites.parse_redis_url() is not None:
            config.state_manager_mode = constants.StateManagerMode.REDIS
        if config.state_manager_mode == constants.StateManagerMode.MEMORY:
            from reflex.istate.manager.memory import StateManagerMemory

            return StateManagerMemory(state=state)
        if config.state_manager_mode == constants.StateManagerMode.DISK:
            from reflex.istate.manager.disk import StateManagerDisk

            return StateManagerDisk(state=state)
        if config.state_manager_mode == constants.StateManagerMode.REDIS:
            redis = prerequisites.get_redis()
            if redis is not None:
                from reflex.istate.manager.redis import StateManagerRedis

                # make sure expiration values are obtained only from the config object on creation
                return StateManagerRedis(
                    state=state,
                    redis=redis,
                    token_expiration=config.redis_token_expiration,
                    lock_expiration=config.redis_lock_expiration,
                    lock_warning_threshold=config.redis_lock_warning_threshold,
                )
        msg = f"Expected one of: DISK, MEMORY, REDIS, got {config.state_manager_mode}"
        raise InvalidStateManagerModeError(msg)

    @abstractmethod
    async def get_state(self, token: str) -> BaseState:
        """Get the state for a token.

        Args:
            token: The token to get the state for.

        Returns:
            The state for the token.
        """

    @abstractmethod
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

    @abstractmethod
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
        yield self.state()

    async def close(self):  # noqa: B027
        """Close the state manager."""


def _default_token_expiration() -> int:
    """Get the default token expiration time.

    Returns:
        The default token expiration time.
    """
    return get_config().redis_token_expiration


def reset_disk_state_manager():
    """Reset the disk state manager."""
    console.debug("Resetting disk state manager.")
    states_directory = prerequisites.get_states_dir()
    if states_directory.exists():
        for path in states_directory.iterdir():
            path.unlink()


def get_state_manager() -> StateManager:
    """Get the state manager for the app that is currently running.

    Returns:
        The state manager.
    """
    return prerequisites.get_and_validate_app().app.state_manager
