"""A switch component."""

from __future__ import annotations

from reflex.components.chakra import ChakraComponent, LiteralColorScheme
from reflex.event import EventHandler
from reflex.vars import Var


class Switch(ChakraComponent):
    """Toggleable switch component."""

    tag = "Switch"

    # If true, the switch will be checked. You'll need to set an on_change event handler to update its value (since it is now controlled)
    is_checked: Var[bool]

    # If true, the switch will be disabled
    is_disabled: Var[bool]

    # If true and is_disabled prop is set, the switch will remain tabbable but not interactive.
    is_focusable: Var[bool]

    # If true, the switch is marked as invalid. Changes style of unchecked state.
    is_invalid: Var[bool]

    # If true, the switch will be readonly
    is_read_only: Var[bool]

    # If true, the switch will be required
    is_required: Var[bool]

    # The name of the input field in a switch (Useful for form submission).
    name: Var[str]

    # The value of the input field when checked (use is_checked prop for a bool)
    value: Var[str] = Var.create(True)  # type: ignore

    # The spacing between the switch and its label text (0.5rem)
    spacing: Var[str]

    # The placeholder text.
    placeholder: Var[str]

    # The color scheme of the switch (e.g. "blue", "green", "red", etc.)
    color_scheme: Var[LiteralColorScheme]

    # Fired when the switch value changes
    on_change: EventHandler[lambda e0: [e0.target.checked]]
