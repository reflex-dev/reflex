"""State manager for managing client states."""

import contextlib
import dataclasses
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, TypedDict, overload

from reflex_base import constants
from reflex_base.config import get_config
from reflex_base.event import Event
from reflex_base.utils.exceptions import InvalidStateManagerModeError
from typing_extensions import ReadOnly, Unpack, deprecated

from reflex.istate.manager.token import TOKEN_TYPE, StateToken
from reflex.utils import console, prerequisites

if TYPE_CHECKING:
    from reflex.state import BaseState


class StateModificationContext(TypedDict, total=False):
    """The context for modifying state."""

    event: ReadOnly[Event | None]


EmptyContext = StateModificationContext()


@dataclasses.dataclass
class StateManager(ABC):
    """A class to manage many client states."""

    @property
    def state(self):
        """Get the state class.

        Deprecated: the state manager no longer holds a reference to the state class.

        Returns:
            The State class.
        """
        console.deprecate(
            feature_name="StateManager.state",
            reason="The state manager no longer holds a reference to the state class. "
            "Use reflex.state.State directly instead.",
            deprecation_version="0.9.0",
            removal_version="1.0",
        )
        from reflex.state import State

        return State

    @classmethod
    def create(cls):
        """Create a new state manager.

        Returns:
            The state manager (either disk, memory or redis).

        Raises:
            InvalidStateManagerModeError: If the state manager mode is invalid.
        """
        config = get_config()
        if (
            "state_manager_mode" not in config._non_default_attributes
            and prerequisites.parse_redis_url() is not None
        ):
            config.state_manager_mode = constants.StateManagerMode.REDIS
        if config.state_manager_mode == constants.StateManagerMode.MEMORY:
            from reflex.istate.manager.memory import StateManagerMemory

            return StateManagerMemory()
        if config.state_manager_mode == constants.StateManagerMode.DISK:
            from reflex.istate.manager.disk import StateManagerDisk

            return StateManagerDisk()
        if config.state_manager_mode == constants.StateManagerMode.REDIS:
            redis = prerequisites.get_redis()
            if redis is not None:
                from reflex.istate.manager.redis import StateManagerRedis

                # make sure expiration values are obtained only from the config object on creation
                return StateManagerRedis(
                    redis=redis,
                    token_expiration=config.redis_token_expiration,
                    lock_expiration=config.redis_lock_expiration,
                    lock_warning_threshold=config.redis_lock_warning_threshold,
                )
        msg = f"Expected one of: DISK, MEMORY, REDIS, got {config.state_manager_mode}"
        raise InvalidStateManagerModeError(msg)

    @staticmethod
    def _coerce_token(token: StateToken[TOKEN_TYPE] | str) -> StateToken[TOKEN_TYPE]:
        """Convert a legacy string token to a StateToken if needed.

        Args:
            token: The token, either a StateToken or legacy string.

        Returns:
            The coerced StateToken.
        """
        if isinstance(token, str):
            from reflex.istate.manager.token import BaseStateToken
            from reflex.state import State

            return BaseStateToken.from_legacy_token(token, root_state=State)  # type: ignore[return-value]
        return token

    @overload
    @deprecated("pass token as rx.BaseStateToken instead of str")
    async def get_state(self, token: str) -> "BaseState": ...

    @overload
    async def get_state(self, token: StateToken[TOKEN_TYPE]) -> TOKEN_TYPE: ...

    @overload
    @deprecated("pass token as rx.BaseStateToken instead of str")
    async def set_state(
        self,
        token: str,
        state: "BaseState",
        **context: Unpack[StateModificationContext],
    ) -> None: ...

    @overload
    async def set_state(
        self,
        token: StateToken[TOKEN_TYPE],
        state: TOKEN_TYPE,
        **context: Unpack[StateModificationContext],
    ) -> None: ...

    @overload
    @deprecated("pass token as rx.BaseStateToken instead of str")
    def modify_state(
        self, token: str, **context: Unpack[StateModificationContext]
    ) -> contextlib.AbstractAsyncContextManager["BaseState"]: ...

    @overload
    def modify_state(
        self,
        token: StateToken[TOKEN_TYPE],
        **context: Unpack[StateModificationContext],
    ) -> contextlib.AbstractAsyncContextManager[TOKEN_TYPE]: ...

    @overload
    @deprecated("pass token as rx.BaseStateToken instead of str")
    def modify_state_with_links(
        self,
        token: str,
        previous_dirty_vars: dict[str, set[str]] | None = None,
        **context: Unpack[StateModificationContext],
    ) -> contextlib.AbstractAsyncContextManager["BaseState"]: ...

    @overload
    def modify_state_with_links(
        self,
        token: StateToken[TOKEN_TYPE],
        previous_dirty_vars: dict[str, set[str]] | None = None,
        **context: Unpack[StateModificationContext],
    ) -> contextlib.AbstractAsyncContextManager[TOKEN_TYPE]: ...

    @abstractmethod
    async def get_state(self, token: StateToken[TOKEN_TYPE] | str) -> TOKEN_TYPE:
        """Get the state for a token.

        Args:
            token: The token to get the state for.

        Returns:
            The state for the token.
        """

    @abstractmethod
    async def set_state(
        self,
        token: StateToken[TOKEN_TYPE] | str,
        state: TOKEN_TYPE,
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
        self,
        token: StateToken[TOKEN_TYPE] | str,
        **context: Unpack[StateModificationContext],
    ) -> AsyncIterator[TOKEN_TYPE]:
        """Modify the state for a token while holding exclusive lock.

        Args:
            token: The token to modify the state for.
            context: The state modification context.

        Yields:
            The state for the token.
        """
        yield  # pyright: ignore[reportReturnType]

    @contextlib.asynccontextmanager
    async def modify_state_with_links(
        self,
        token: StateToken[TOKEN_TYPE] | str,
        previous_dirty_vars: dict[str, set[str]] | None = None,
        **context: Unpack[StateModificationContext],
    ) -> AsyncIterator[TOKEN_TYPE]:
        """Modify the state for a token, including linked substates, while holding exclusive lock.

        Args:
            token: The token to modify the state for.
            previous_dirty_vars: The previously dirty vars for linked states.
            context: The state modification context.

        Yields:
            The state for the token with linked states patched in.
        """
        from reflex.state import BaseState

        token = self._coerce_token(token)
        async with self.modify_state(token, **context) as root_state:
            if (
                isinstance(root_state, BaseState)
                and getattr(root_state, "_reflex_internal_links", None) is not None
            ):
                from reflex.istate.shared import SharedStateBaseInternal

                shared_state = await root_state.get_state(SharedStateBaseInternal)
                async with shared_state._modify_linked_states(
                    previous_dirty_vars=previous_dirty_vars
                ) as _:
                    yield root_state
            else:
                yield root_state

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
    from reflex_base.event.context import EventContext

    return EventContext.get().state_manager
