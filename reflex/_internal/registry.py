"""A contextual registry for state and event handlers."""

import dataclasses
from typing import TYPE_CHECKING, Self

from reflex._internal.context.base import BaseContext

if TYPE_CHECKING:
    from reflex.event import EventHandler
    from reflex.state import BaseState


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class RegisteredEventHandler:
    """A registered event handler, which includes the handler and its full name."""

    handler: EventHandler
    states: tuple[type[BaseState], ...]


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True, eq=False)
class RegistrationContext(BaseContext):
    """Context for registering event handlers and states."""

    event_handlers: dict[str, RegisteredEventHandler] = dataclasses.field(
        default_factory=dict,
        repr=False,
    )
    base_states: dict[str, type[BaseState]] = dataclasses.field(
        default_factory=dict,
        repr=False,
    )

    @classmethod
    def ensure_context(cls) -> Self:
        """Ensure the context is attached, or create a new instance and attach it.

        Returns:
            The registration context instance.
        """
        try:
            return cls.get()
        except LookupError:
            # If the context is not attached, create a new instance and attach it.
            ctx = cls()
            cls._context_var.set(ctx)
            return ctx

    @classmethod
    def register_base_state(cls, state_cls: type[BaseState]) -> type[BaseState]:
        """Register a base state class with its full name.

        Args:
            state_cls: The base state class to register.

        Returns:
            The registered base state class.
        """
        cls.ensure_context().base_states[state_cls.get_full_name()] = state_cls
        return state_cls

    @classmethod
    def register_event_handler(
        cls, handler: EventHandler, states: tuple[type[BaseState], ...] = ()
    ) -> EventHandler:
        """Register an event handler with its full name and associated states.

        Args:
            handler: The event handler to register.
            states: The states associated with the event handler.

        Returns:
            The registered event handler.
        """
        from reflex.utils.format import format_event_handler

        full_name = format_event_handler(handler)
        cls.ensure_context().event_handlers[full_name] = RegisteredEventHandler(
            handler=handler, states=states
        )
        return handler
