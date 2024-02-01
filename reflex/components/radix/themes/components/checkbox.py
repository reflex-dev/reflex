"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal

from reflex.components.component import Component
from reflex.components.radix.themes.layout.flex import Flex
from reflex.components.radix.themes.typography.text import Text
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    LiteralSize,
    LiteralVariant,
    RadixThemesComponent,
)

LiteralCheckboxSize = Literal["1", "2", "3"]


class Checkbox(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Checkbox"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Button size "1" - "3"
    size: Var[LiteralCheckboxSize]

    # Variant of button: "solid" | "soft" | "outline" | "ghost"
    variant: Var[LiteralVariant]

    # Override theme color for button
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the button with higher contrast color against background
    high_contrast: Var[bool]

    # Whether the checkbox is checked by default
    default_checked: Var[bool]

    # Whether the checkbox is checked
    checked: Var[bool]

    # Whether the checkbox is disabled
    disabled: Var[bool]

    # Whether the checkbox is required
    required: Var[bool]

    # The name of the checkbox control when submitting the form.
    name: Var[str]

    # The value of the checkbox control when submitting the form.
    value: Var[str]

    # Props to rename
    _rename_props = {"onChange": "onCheckedChange"}

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_CHANGE: lambda e0: [e0],
        }


class HighLevelCheckbox(Checkbox):
    """A checkbox component with a label."""

    # The text label for the checkbox.
    text: Var[str]

    # The gap between the checkbox and the label.
    gap: Var[LiteralSize]

    # The size of the checkbox.
    size: Var[LiteralCheckboxSize]

    @classmethod
    def create(cls, text: Var[str] = Var.create_safe(""), **props) -> Component:
        """Create a checkbox with a label.

        Args:
            text: The text of the label.
            **props: Additional properties to apply to the checkbox item.

        Returns:
            The checkbox component with a label.
        """
        gap = props.pop("gap", "2")
        size = props.pop("size", "2")

        return Text.create(
            Flex.create(
                Checkbox.create(
                    size=size,
                    **props,
                ),
                text,
                gap=gap,
            ),
            as_="label",
            size=size,
        )
