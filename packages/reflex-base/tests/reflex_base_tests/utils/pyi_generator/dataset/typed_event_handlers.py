"""Components with various event handler signatures.

This module tests:
- Custom event handlers with typed tuple returns
- passthrough_event_spec usage
- Multiple event specs (Sequence of specs)
- Event handlers with no args (no_args_event_spec)
- Event handler with multi-arg tuples
- String-based tuple return annotations
"""

from reflex_base.components.component import Component, field
from reflex_base.event import EventHandler, passthrough_event_spec
from reflex_base.vars.base import Var


def on_value_change_handler(value: Var[str]) -> tuple[Var[str]]:
    """Event spec for a string value change.

    Args:
        value: The new value.

    Returns:
        The value tuple.
    """
    return (value,)


def on_pair_change_handler(key: Var[str], value: Var[int]) -> tuple[Var[str], Var[int]]:
    """Event spec for a key-value pair change.

    Args:
        key: The key.
        value: The value.

    Returns:
        The key-value tuple.
    """
    return (key, value)


class EventComponent(Component):
    """A component with various event handler types."""

    # A simple string value prop.
    value: Var[str]

    # Custom event handler with typed return.
    on_value_change: EventHandler[on_value_change_handler] = field(
        doc="Fired when the value changes.",
    )

    # Event handler with multiple return args.
    on_pair_change: EventHandler[on_pair_change_handler] = field(
        doc="Fired when a key-value pair changes.",
    )

    # Passthrough event spec with single type.
    on_item_select: EventHandler[passthrough_event_spec(str)] = field(
        doc="Fired when an item is selected.",
    )

    # Passthrough event spec with multiple types.
    on_range_change: EventHandler[passthrough_event_spec(int, int)] = field(
        doc="Fired when the range changes.",
    )


class MultiSpecComponent(Component):
    """A component where event triggers have multiple possible specs."""

    value: Var[str]

    # Multiple event specs: can fire with no args or with a string value.
    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when the open state changes.",
    )
