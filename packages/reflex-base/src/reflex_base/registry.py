"""A contextual registry for state and event handlers.

The registry owns three kinds of bookkeeping:

* the set of registered ``BaseState`` subclasses and their parent/child topology
* the set of registered ``EventHandler`` instances keyed by their full dotted name
* the **name resolution** strategy that turns a state class or handler name into the
  string used by the rest of the framework

The third concern is pluggable through the :class:`NameResolver` protocol. The
default resolver is a no-op (every state and handler keeps its built-in name).
``reflex.minify`` ships a :class:`MinifyNameResolver` that consults
``minify.json``; users can plug in their own (custom prefixes, multi-tenant
aliasing, deterministic test fixtures, etc.) by calling
:meth:`RegistrationContext.set_name_resolver`.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from typing_extensions import Self

from reflex_base.context.base import BaseContext
from reflex_base.utils.exceptions import StateValueError

if TYPE_CHECKING:
    from reflex.state import BaseState
    from reflex_base.components.component import StatefulComponent
    from reflex_base.event import EventHandler


@runtime_checkable
class NameResolver(Protocol):
    """Resolves the user-visible names for state classes and event handlers.

    Implementations may apply minification, prefixing, locale-based aliasing,
    or any other transformation. Returning ``None`` from either method means
    "no override — use the default name".

    The protocol is intentionally tiny so resolvers compose well; see
    :class:`DefaultNameResolver` for the no-op base case and
    ``reflex.minify.MinifyNameResolver`` for the canonical example of a
    resolver that consults external configuration.
    """

    def resolve_state_name(self, state_cls: type[BaseState]) -> str | None:
        """Return the resolved name for ``state_cls``, or ``None`` for default."""
        ...

    def resolve_handler_name(
        self, state_cls: type[BaseState], handler_name: str
    ) -> str | None:
        """Return the resolved name for the handler, or ``None`` for default."""
        ...


@dataclasses.dataclass(frozen=True, slots=True)
class DefaultNameResolver:
    """No-op resolver — every state and handler keeps its default name."""

    def resolve_state_name(self, state_cls: type[BaseState]) -> str | None:  # noqa: D102
        return None

    def resolve_handler_name(  # noqa: D102
        self,
        state_cls: type[BaseState],
        handler_name: str,
    ) -> str | None:
        return None


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
    tag_to_stateful_component: dict[str, StatefulComponent] = dataclasses.field(
        default_factory=dict,
        repr=False,
    )
    name_resolver: NameResolver = dataclasses.field(
        default_factory=DefaultNameResolver,
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

    @staticmethod
    def default_state_name(state_cls: type[BaseState]) -> str:
        """Compute the built-in name for a state class (no resolver applied).

        This is the snake-cased ``module___ClassName`` form used when no
        resolver overrides it.

        Args:
            state_cls: The state class.

        Returns:
            The default name.
        """
        from reflex.utils import format

        module = state_cls.__module__.replace(".", "___")
        return format.to_snake_case(f"{module}___{state_cls.__name__}")

    def get_state_name(self, state_cls: type[BaseState]) -> str:
        """Resolve the user-visible name for a state class.

        Asks the installed :class:`NameResolver` first; falls back to
        :meth:`default_state_name` when the resolver returns ``None``.

        Args:
            state_cls: The state class.

        Returns:
            The resolved name.
        """
        resolved = self.name_resolver.resolve_state_name(state_cls)
        if resolved is not None:
            return resolved
        return self.default_state_name(state_cls)

    def get_handler_name(self, state_cls: type[BaseState], handler_name: str) -> str:
        """Resolve the user-visible name for an event handler.

        Asks the installed :class:`NameResolver` first; falls back to the
        original ``handler_name`` when the resolver returns ``None``.

        Args:
            state_cls: The state class the handler is attached to.
            handler_name: The original (Python) name of the handler.

        Returns:
            The resolved name.
        """
        resolved = self.name_resolver.resolve_handler_name(state_cls, handler_name)
        if resolved is not None:
            return resolved
        return handler_name

    def set_name_resolver(self, resolver: NameResolver) -> None:
        """Install ``resolver`` and propagate the new names through the registry.

        Concretely: clears the per-class ``get_name``/``get_full_name``/
        ``get_class_substate`` lru_caches on every registered state and calls
        :meth:`refresh_keys` so the registry's name-keyed dicts reflect what
        the new resolver returns.

        ``resolver`` is stored even on a ``frozen`` dataclass via
        ``object.__setattr__`` — the field is conceptually mutable while the
        rest of the context shape stays immutable.

        Args:
            resolver: The resolver to install. Pass :class:`DefaultNameResolver`
                to revert to built-in names.
        """
        object.__setattr__(self, "name_resolver", resolver)
        for cls in self.base_states.values():
            cls.get_name.cache_clear()
            cls.get_full_name.cache_clear()
            cls.get_class_substate.cache_clear()
        self.refresh_keys()

    def refresh_keys(self) -> None:
        """Re-key all registered classes/handlers using current full names.

        State minification rewrites ``BaseState.get_name()``, but the registry
        uses ``parent.get_full_name()`` as the dict key at registration time.
        If the minify config (or env var) changes after a class was registered,
        lookups will miss. Call this after ``minify.clear_config_cache()`` to
        rebuild the dicts with the current names.

        Builds the replacement dicts before mutating ``self`` so a failure
        partway through (e.g. an unreadable minify.json that makes
        ``format_event_handler`` raise) leaves the existing registry intact.
        """
        from reflex.utils.format import format_event_handler

        all_classes = list(self.base_states.values())
        new_base_states: dict[str, type[BaseState]] = {}
        new_substates: dict[str, set[type[BaseState]]] = {}
        for cls in all_classes:
            new_base_states[cls.get_full_name()] = cls
            parent = cls.get_parent_state()
            if parent is not None:
                new_substates.setdefault(parent.get_full_name(), set()).add(cls)

        all_handlers = list(self.event_handlers.values())
        new_handlers: dict[str, RegisteredEventHandler] = {
            format_event_handler(reg.handler): reg for reg in all_handlers
        }

        self.base_states.clear()
        self.base_states.update(new_base_states)
        self.base_state_substates.clear()
        self.base_state_substates.update(new_substates)
        self.event_handlers.clear()
        self.event_handlers.update(new_handlers)
