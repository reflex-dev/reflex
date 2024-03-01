"""A checkbox component."""
from __future__ import annotations

from typing import Any, Optional, Union

from reflex.components.chakra import (
    ChakraComponent,
    LiteralColorScheme,
    LiteralTagSize,
)
from reflex.constants import EventTriggers
from reflex.vars import Var


class Checkbox(ChakraComponent):
    """The Checkbox component is used in forms when a user needs to select multiple values from several options."""

    tag: str = "Checkbox"

    # Color scheme for checkbox.
    # Options:
    # "whiteAlpha" | "blackAlpha" | "gray" | "red" | "orange" | "yellow" | "green" | "teal" | "blue" | "cyan"
    # | "purple" | "pink" | "linkedin" | "facebook" | "messenger" | "whatsapp" | "twitter" | "telegram"
    color_scheme: Optional[Var[LiteralColorScheme]] = None

    # "sm" | "md" | "lg"
    size: Optional[Var[LiteralTagSize]] = None

    # If true, the checkbox will be checked.
    is_checked: Optional[Var[bool]] = None

    # If true, the checkbox will be disabled
    is_disabled: Optional[Var[bool]] = None

    # If true and is_disabled is passed, the checkbox will remain tabbable but not interactive
    is_focusable: Optional[Var[bool]] = None

    # If true, the checkbox will be indeterminate. This only affects the icon shown inside checkbox and does not modify the is_checked var.
    is_indeterminate: Optional[Var[bool]] = None

    # If true, the checkbox is marked as invalid. Changes style of unchecked state.
    is_invalid: Optional[Var[bool]] = None

    # If true, the checkbox will be readonly
    is_read_only: Optional[Var[bool]] = None

    # If true, the checkbox input is marked as required, and required attribute will be added
    is_required: Optional[Var[bool]] = None

    # The name of the input field in a checkbox (Useful for form submission).
    name: Optional[Var[str]] = None

    # The value of the input field when checked (use is_checked prop for a bool)
    value: Var[str] = Var.create("true")  # type: ignore

    # The spacing between the checkbox and its label text (0.5rem)
    spacing: Optional[Var[str]] = None

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_CHANGE: lambda e0: [e0.target.checked],
        }


class CheckboxGroup(ChakraComponent):
    """A group of checkboxes."""

    tag: str = "CheckboxGroup"

    # The value of the checkbox group
    value: Optional[Var[str]] = None

    # The initial value of the checkbox group
    default_value: Optional[Var[str]] = None

    # If true, all wrapped checkbox inputs will be disabled
    is_disabled: Optional[Var[bool]] = None

    # If true, input elements will receive checked attribute instead of isChecked. This assumes, you're using native radio inputs
    is_native: Optional[Var[bool]] = None
