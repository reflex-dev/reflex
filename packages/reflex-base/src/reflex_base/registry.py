"""A contextual registry for state and event handlers."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, TypeVar

from typing_extensions import Self

from reflex_base.context.base import BaseContext
from reflex_base.utils.exceptions import StateValueError

if TYPE_CHECKING:
    from reflex.state import BaseState
    from reflex_base.event import EventHandler

STATE_TYPE = TypeVar("STATE_TYPE", bound="BaseState")


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
    base_state_substates: dict[str, set[type[BaseState]]] = dataclasses.field(
        default_factory=dict,
        repr=False,
    )
    # Memoized lookups, invalidated whenever a base state is registered.
    _implementations: dict[type[BaseState], tuple[type[BaseState], ...]] = (
        dataclasses.field(
            default_factory=dict,
            repr=False,
        )
    )
    _resolved_implementations: dict[type[BaseState], type[BaseState]] = (
        dataclasses.field(
            default_factory=dict,
            repr=False,
        )
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

        Also registers parent_state until finding one that is already registered.

        Args:
            state_cls: The base state class to register.

        Returns:
            The registered base state class.
        """
        return cls.ensure_context()._register_base_state(state_cls)

    def _register_base_state(self, state_cls: type[BaseState]) -> type[BaseState]:
        """Register a base state class with its full name.

        Also registers parent_state until finding one that is already registered.

        Args:
            state_cls: The base state class to register.

        Returns:
            The registered base state class.
        """
        self.base_states[state_cls.get_full_name()] = state_cls
        self._implementations.clear()
        self._resolved_implementations.clear()
        for event_handler in state_cls.event_handlers.values():
            self._register_event_handler(event_handler, states=(state_cls,))
        if (parent_state := state_cls.get_parent_state()) is not None:
            if parent_state.get_full_name() not in self.base_states:
                self._register_base_state(parent_state)
            parent_state_substates = self.base_state_substates.setdefault(
                parent_state.get_full_name(), set()
            )
            if state_cls in parent_state_substates:
                msg = (
                    f"State class {state_cls.get_full_name()} is already registered as a substate of "
                    f"{parent_state.get_full_name()}. This likely means there are multiple classes with the same name "
                    "in the same module, which causes a conflict in the registry. Please rename one of the classes to avoid "
                    "shadowing. Shadowing substate classes is not allowed."
                )
                raise StateValueError(msg)
            parent_state_substates.add(state_cls)
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
        return cls.ensure_context()._register_event_handler(handler, states=states)

    def _register_event_handler(
        self,
        handler: EventHandler,
        states: tuple[type[BaseState], ...] = (),
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
        self.event_handlers[full_name] = RegisteredEventHandler(
            handler=handler, states=states
        )
        return handler

    def get_substates(
        self, base_state_cls: type[BaseState] | str
    ) -> set[type[BaseState]]:
        """Get the substates for a base state class.

        Args:
            base_state_cls: The base state class to get substates for.

        Returns:
            A set of substate classes.
        """
        if isinstance(base_state_cls, str):
            return self.base_state_substates.setdefault(base_state_cls, set())
        return self.base_state_substates.setdefault(
            base_state_cls.get_full_name(), set()
        )

    def get_states_implementing(
        self, interface: type[STATE_TYPE]
    ) -> tuple[type[STATE_TYPE], ...]:
        """Get every registered state class that is a subclass of the given interface.

        Args:
            interface: The state mixin (or state class) to look up implementations of.

        Returns:
            The registered states implementing the interface, in registration order.
        """
        if (cached := self._implementations.get(interface)) is not None:
            return cached  # pyright: ignore [reportReturnType]
        implementations = tuple(
            state_cls
            for state_cls in self.base_states.values()
            if issubclass(state_cls, interface)
        )
        self._implementations[interface] = implementations
        return implementations

    def resolve_implementation(self, interface: type[STATE_TYPE]) -> type[STATE_TYPE]:
        """Get the single registered state class the given interface was mixed into.

        Args:
            interface: The state mixin (or state class) to resolve.

        Returns:
            The state class the interface was mixed into.

        Raises:
            StateValueError: If no or more than one state implements the interface.
        """
        if (cached := self._resolved_implementations.get(interface)) is not None:
            return cached  # pyright: ignore [reportReturnType]
        implementations = self.get_states_implementing(interface)
        # Keep only where the interface entered the tree: an implementation
        # inheriting from another implementation is not a candidate.
        roots = [
            state_cls
            for state_cls in implementations
            if not any(
                other is not state_cls and issubclass(state_cls, other)
                for other in implementations
            )
        ]
        if not roots:
            msg = (
                f"No registered state implements {interface.__name__}. "
                "Define a state which inherits from it before resolving it."
            )
            raise StateValueError(msg)
        if len(roots) > 1:
            names = ", ".join(sorted(state.get_full_name() for state in roots))
            msg = (
                f"{interface.__name__} is implemented by more than one state: {names}. "
                "Resolving it is ambiguous, pass the wanted state class explicitly."
            )
            raise StateValueError(msg)
        resolved = roots[0]
        self._resolved_implementations[interface] = resolved
        return resolved
