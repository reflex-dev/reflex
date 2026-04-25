"""Component with various Var[T] prop types and edge cases.

This module tests:
- Var[T] expansion: Var[str] -> Var[str] | str
- Var with Union args: Var[str | int] -> Var[str | int] | str | int
- Complex nested types: Var[list[str]], Var[dict[str, Any]], Var[list[dict[str, Any]]]
- Callable prop: Var[Callable[[], bool]] (should NOT expand inner type)
- Component with no custom props (just inherited defaults)
- Component with only event handlers (no data props)
"""

from collections.abc import Callable
from typing import Any

from reflex_base.components.component import Component, field
from reflex_base.event import EventHandler, passthrough_event_spec
from reflex_base.vars.base import Var


class EmptyComponent(Component):
    """A component with no custom props at all."""


class EventOnlyComponent(Component):
    """A component with only custom event handlers, no data props."""

    on_toggle: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when toggled.",
    )


class VarTypesComponent(Component):
    """A component exercising various Var type expansions."""

    # Basic Var types.
    name: Var[str]
    count: Var[int]
    ratio: Var[float]
    flag: Var[bool]

    # Union inside Var.
    value: Var[str | int] = field(doc="A string or int value.")

    # Nested generic Var types.
    items: Var[list[str]] = field(doc="A list of string items.")
    metadata: Var[dict[str, Any]] = field(doc="Metadata dictionary.")
    nested: Var[list[dict[str, Any]]] = field(doc="Nested structures.")

    # Callable prop — the inner Callable type should not be expanded.
    on_check: Var[Callable[[], bool]] = field(doc="A callable that returns bool.")
