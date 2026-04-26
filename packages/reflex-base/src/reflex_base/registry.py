"""Contextual registry for state classes, event handlers, and the
:class:`NameResolver` strategy that turns them into user-visible names.

The default resolver is a no-op; ``reflex.minify.MinifyNameResolver``
plugs in a :class:`minify.json`-driven implementation. Install a custom
resolver via :meth:`RegistrationContext.set_name_resolver`.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

from typing_extensions import Self

from reflex_base.context.base import BaseContext
from reflex_base.utils.exceptions import StateValueError

if TYPE_CHECKING:
    from reflex.state import BaseState
    from reflex_base.components.component import StatefulComponent
    from reflex_base.event import EventHandler

_T = TypeVar("_T")


def _rekey(
    items: Iterable[_T], key_fn: Callable[[_T], str], kind: str
) -> dict[str, _T]:
    """Build a name-keyed dict, warning on collisions.

    Args:
        items: Source items to re-key.
        key_fn: Computes the new key for each item.
        kind: Human-readable noun for the collision warning (e.g. ``"state class"``).

    Returns:
        A new dict mapping resolved key to item; later items overwrite earlier.
    """
    from reflex.utils import console

    out: dict[str, _T] = {}
    for item in items:
        key = key_fn(item)
        existing = out.get(key)
        if existing is not None and existing is not item:
            console.warn(
                f"Two {kind}s resolve to the same full name {key!r}: "
                f"{existing!r} and {item!r}. The first one will be unreachable "
                "in the registry. Check minify.json for duplicate ids."
            )
        out[key] = item
    return out


@runtime_checkable
class NameResolver(Protocol):
    """Resolves user-visible names for state classes and event handlers.

    Return ``None`` to defer to the framework default. See
    :class:`DefaultNameResolver` (no-op) and ``reflex.minify.MinifyNameResolver``.
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
    def try_get(cls) -> Self | None:
        """Return the active context, or ``None`` when none is attached.

        Returns:
            The registration context instance, or ``None``.
        """
        try:
            return cls.get()
        except LookupError:
            return None

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
        """Compute the built-in snake-cased ``module___ClassName`` for a state.

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

        Args:
            state_cls: The state class.

        Returns:
            The resolved name (or :meth:`default_state_name` fallback).
        """
        resolved = self.name_resolver.resolve_state_name(state_cls)
        if resolved is not None:
            return resolved
        return self.default_state_name(state_cls)

    def get_handler_name(self, state_cls: type[BaseState], handler_name: str) -> str:
        """Resolve the user-visible name for an event handler.

        Args:
            state_cls: The state class the handler is attached to.
            handler_name: The original (Python) name of the handler.

        Returns:
            The resolved name (or ``handler_name`` unchanged).
        """
        resolved = self.name_resolver.resolve_handler_name(state_cls, handler_name)
        if resolved is not None:
            return resolved
        return handler_name

    def set_name_resolver(self, resolver: NameResolver) -> None:
        """Install ``resolver`` and rebuild the registry under the new names.

        Clears the per-class ``get_name`` / ``get_full_name`` /
        ``get_class_substate`` lru_caches and calls :meth:`refresh_keys`.
        Uses ``object.__setattr__`` to mutate the frozen ``name_resolver``
        slot.

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
        """Re-key the name-keyed dicts using current ``get_full_name`` values.

        Built atomically: the replacement dicts are populated before any of
        ``self`` is mutated, so a partway failure (e.g. malformed minify.json
        making ``format_event_handler`` raise) leaves the existing registry
        intact. A console warning is emitted on full-name collisions —
        usually a sign of duplicate ids in ``minify.json``.
        """
        from reflex.utils.format import format_event_handler

        new_base_states = _rekey(
            self.base_states.values(), lambda c: c.get_full_name(), "state class"
        )
        new_substates: dict[str, set[type[BaseState]]] = {}
        for cls in new_base_states.values():
            parent = cls.get_parent_state()
            if parent is not None:
                new_substates.setdefault(parent.get_full_name(), set()).add(cls)
        new_handlers = _rekey(
            self.event_handlers.values(),
            lambda r: format_event_handler(r.handler),
            "event handler",
        )

        self.base_states.clear()
        self.base_states.update(new_base_states)
        self.base_state_substates.clear()
        self.base_state_substates.update(new_substates)
        self.event_handlers.clear()
        self.event_handlers.update(new_handlers)
