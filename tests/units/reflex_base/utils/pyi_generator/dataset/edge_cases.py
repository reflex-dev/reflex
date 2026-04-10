"""Components with edge case type annotations.

This module tests:
- Var[list[int]] type hint (nested generic inside Var)
- Optional[Var[str]] (explicit Optional wrapping)
- Component with no props (just inherited defaults)
- Component with only event handlers (no data props)
"""

from typing import Any

from reflex_base.components.component import Component, field
from reflex_base.event import EventHandler, passthrough_event_spec
from reflex_base.vars.base import Var


class EmptyComponent(Component):
    """A component with no custom props at all."""

    pass


class EventOnlyComponent(Component):
    """A component with only custom event handlers, no data props."""

    on_toggle: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when toggled.",
    )


class NestedGenericComponent(Component):
    """A component with nested generic Var types."""

    # Var with nested generic.
    numbers: Var[list[int]] = field(doc="A list of numbers.")

    pairs: Var[dict[str, int]] = field(doc="Key-value pairs.")

    nested: Var[list[dict[str, Any]]] = field(doc="Nested structures.")
