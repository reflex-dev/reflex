"""State manager for managing client states."""

import contextlib
import dataclasses
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import TYPE_CHECKING, Any, TypedDict, cast, overload

from reflex_base import constants
from reflex_base.config import get_config
from reflex_base.event import Event
from reflex_base.event.context import EventContext
from reflex_base.utils.exceptions import InvalidStateManagerModeError
from typing_extensions import ReadOnly, Unpack, deprecated

from reflex.istate.manager.token import TOKEN_TYPE, StateToken
from reflex.utils import console, prerequisites

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from reflex.state import BaseState


class StateModificationContext(TypedDict, total=False):
    """The context for modifying state."""

    event: ReadOnly[Event | None]


EmptyContext = StateModificationContext()


@dataclasses.dataclass(frozen=True, slots=True)
class StateLease:
    """Proof that a StateManager lock is held on an ident."""

    # The locked ident.
    ident: str

    # Identifies this holder of the lock, for managers that check it on store.
    lock_id: bytes | None = None


@dataclasses.dataclass
class StateManager(ABC):
    """A class to manage many client states."""

    @property
    def state(self):
        """The state class.

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

    @abstractmethod
    async def load_states(
        self, tokens: Sequence[StateToken], *, create: bool = True
    ) -> list[Any]:
        """Load the stored states for some tokens.

        Args:
            tokens: The tokens of the states to load.
            create: Whether to create the states that are not stored, with
                ``token.new_instance()``. Otherwise they are None.

        Returns:
            The state for each token, in order.
        """

    @abstractmethod
    async def store_states(
        self,
        states: Sequence[tuple[StateToken, Any]],
        lease: StateLease | None,
        **context: Unpack[StateModificationContext],
    ) -> None:
        """Store states, skipping the ones not touched since they were stored.

        Args:
            states: The tokens and states to store.
            lease: The lease of the lock held on the states' ident, if any.
            context: The state modification context.
        """

    @abstractmethod
    def lock(
        self, token: StateToken, **context: Unpack[StateModificationContext]
    ) -> contextlib.AbstractAsyncContextManager[StateLease]:
        """Hold the exclusive lock on a token's ident.

        Args:
            token: The token to lock.
            context: The state modification context.

        Returns:
            A context manager holding the lock, yielding its lease.
        """

    def _state_context(self, ident: str) -> EventContext:
        """Get an EventContext to check out an ident's states with this manager.

        Args:
            ident: The ident of the states.

        Returns:
            The current EventContext when it is for this ident and manager,
            otherwise a new one.
        """
        try:
            ctx = EventContext.get()
        except LookupError:
            return EventContext(
                token=ident, state_manager=self, enqueue_impl=_no_enqueue
            )
        if ctx.token == ident and ctx.state_manager is self:
            return ctx
        ctx = ctx.fork(token=ident)
        if ctx.state_manager is not self:
            ctx = dataclasses.replace(ctx, state_manager=self)
        return ctx

    @overload
    @deprecated("pass token as rx.BaseStateToken instead of str")
    async def get_state(self, token: str) -> "BaseState": ...

    @overload
    async def get_state(self, token: StateToken[TOKEN_TYPE]) -> TOKEN_TYPE: ...

    async def get_state(self, token: StateToken[TOKEN_TYPE] | str) -> TOKEN_TYPE:
        """Get the state for a token.

        Args:
            token: The token to get the state for.

        Returns:
            The state for the token, the root of its tree for a BaseStateToken.
        """
        token = self._coerce_token(token)
        ctx = self._state_context(token.ident)
        return _legacy_state(token, await ctx.get_state(token))

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

    async def set_state(
        self,
        token: StateToken[TOKEN_TYPE] | str,
        state: TOKEN_TYPE,
        **context: Unpack[StateModificationContext],
    ) -> None:
        """Replace the stored state for a token.

        Args:
            token: The token to set the state for.
            state: The state to set, with its substates for a BaseStateToken.
            context: The state modification context.
        """
        from reflex.istate.manager.token import BaseStateToken

        token = self._coerce_token(token)
        if not isinstance(token, BaseStateToken):
            await self.store_states([(token, state)], None, **context)
            return
        states = []
        pending: list[BaseState] = [cast("BaseState", state)]
        while pending:
            substate = pending.pop()
            # A replacement is stored whole, touched or not.
            substate._was_touched = True
            states.append((token.with_cls(type(substate)), substate))
            pending.extend(substate.substates.values())
        await self.store_states(states, None, **context)

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
            The state for the token, the root of its tree for a BaseStateToken.
        """
        token = self._coerce_token(token)
        with _entered(self._state_context(token.ident)) as ctx:
            async with ctx.modify_state(token, **context) as state:
                yield _legacy_state(token, state)

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
            The state for the token with linked states patched in, the root of
            its tree for a BaseStateToken.
        """
        token = self._coerce_token(token)
        with _entered(self._state_context(token.ident)) as ctx:
            async with modify_state_with_links(
                ctx, token, previous_dirty_vars, **context
            ) as state:
                yield _legacy_state(token, state)

    async def close(self):  # noqa: B027
        """Close the state manager."""


async def _no_enqueue(token: str, *events: Event) -> None:  # noqa: RUF029
    """Refuse to enqueue events outside of event processing.

    Args:
        token: The client token.
        events: The events to enqueue.

    Raises:
        RuntimeError: Always.
    """
    msg = "Events cannot be enqueued outside of event processing."
    raise RuntimeError(msg)


@contextlib.contextmanager
def _entered(ctx: EventContext) -> Iterator[EventContext]:
    """Make an EventContext the current one, unless it already is.

    Args:
        ctx: The context.

    Yields:
        The context.
    """
    try:
        current = EventContext.get()
    except LookupError:
        current = None
    if current is ctx:
        yield ctx
        return
    reset_token = EventContext.set(ctx)
    try:
        yield ctx
    finally:
        EventContext.reset(reset_token)


def _legacy_state(token: StateToken[TOKEN_TYPE], state: TOKEN_TYPE) -> TOKEN_TYPE:
    """Get the state the legacy StateManager methods return for a token.

    Args:
        token: The token of the state.
        state: The state checked out for the token.

    Returns:
        The root of the state's tree for a BaseStateToken, otherwise the state.
    """
    from reflex.istate.manager.token import BaseStateToken

    if isinstance(token, BaseStateToken):
        return cast("TOKEN_TYPE", cast("BaseState", state)._get_root_state())
    return state


@contextlib.asynccontextmanager
async def modify_state_with_links(
    ctx: EventContext,
    token: StateToken[TOKEN_TYPE],
    previous_dirty_vars: dict[str, set[str]] | None = None,
    **context: Unpack[StateModificationContext],
) -> AsyncIterator[TOKEN_TYPE]:
    """Modify a state in an EventContext, with the linked states patched into its tree.

    Args:
        ctx: The event context to check out the state in.
        token: The token of the state.
        previous_dirty_vars: The previously dirty vars for linked states.
        context: The state modification context.

    Yields:
        The state checked out for the token.
    """
    from reflex.state import BaseState

    async with ctx.modify_state(token, **context) as state:
        if (
            isinstance(state, BaseState)
            and getattr(
                root_state := state._get_root_state(), "_reflex_internal_links", None
            )
            is not None
        ):
            from reflex.istate.shared import SharedStateBaseInternal

            shared_state = await root_state.get_state(SharedStateBaseInternal)
            if shared_state._exit_stack is not None:
                # Re-entered by the task holding the lock: the linked states
                # are already patched in, and handled when it leaves.
                yield state
                return
            async with shared_state._modify_linked_states(
                previous_dirty_vars=previous_dirty_vars
            ):
                yield state
        else:
            yield state


def _default_token_expiration() -> int:
    """Get the default token expiration time.

    Returns:
        The default token expiration time.
    """
    return get_config().redis_token_expiration


def reset_disk_state_manager():
    """Reset the disk state manager."""
    logger.debug("Resetting disk state manager.")
    states_directory = prerequisites.get_states_dir()
    if states_directory.exists():
        for path in states_directory.iterdir():
            path.unlink()


def get_state_manager() -> StateManager:
    """Get the state manager for the app that is currently running.

    Returns:
        The state manager.
    """
    return EventContext.get().state_manager
