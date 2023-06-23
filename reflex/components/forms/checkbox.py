"""A checkbox component."""

from typing import Dict

from reflex.components.component import EVENT_ARG
from reflex.components.libs.chakra import ChakraComponent
from reflex.vars import Var


class Checkbox(ChakraComponent):
    """The Checkbox component is used in forms when a user needs to select multiple values from several options."""

    tag = "Checkbox"

    # Color scheme for checkbox.
    # Options:
    # "whiteAlpha" | "blackAlpha" | "gray" | "red" | "orange" | "yellow" | "green" | "teal" | "blue" | "cyan"
    # | "purple" | "pink" | "linkedin" | "facebook" | "messenger" | "whatsapp" | "twitter" | "telegram"
    color_scheme: Var[str]

    # "sm" | "md" | "lg"
    size: Var[str]

    # If true, the checkbox will be checked.
    is_checked: Var[bool]

    # If true, the checkbox will be disabled
    is_disabled: Var[bool]

    # If true and is_disabled is passed, the checkbox will remain tabbable but not interactive
    is_focusable: Var[bool]

    # If true, the checkbox will be indeterminate. This only affects the icon shown inside checkbox and does not modify the is_checked var.
    is_indeterminate: Var[bool]

    # If true, the checkbox is marked as invalid. Changes style of unchecked state.
    is_invalid: Var[bool]

    # If true, the checkbox will be readonly
    is_read_only: Var[bool]

    # If true, the checkbox input is marked as required, and required attribute will be added
    is_required: Var[bool]

    # The name of the input field in a checkbox (Useful for form submission).
    name: Var[str]

    # The spacing between the checkbox and its label text (0.5rem)
    spacing: Var[str]

    def get_controlled_triggers(self) -> Dict[str, Var]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            "on_change": EVENT_ARG.target.checked,
        }


class CheckboxGroup(ChakraComponent):
    """A group of checkboxes."""

    tag = "CheckboxGroup"

    # The value of the checkbox group
    value: Var[str]

    # The initial value of the checkbox group
    default_value: Var[str]

    # If true, all wrapped checkbox inputs will be disabled
    is_disabled: Var[bool]

    # If true, input elements will receive checked attribute instead of isChecked. This assumes, you're using native radio inputs
    is_native: Var[bool]
