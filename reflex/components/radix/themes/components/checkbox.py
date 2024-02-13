"""Interactive components provided by @radix-ui/themes."""
from types import SimpleNamespace
from typing import Any, Dict, Literal

from reflex.components.component import Component
from reflex.components.radix.themes.layout.flex import Flex
from reflex.components.radix.themes.typography.text import Text
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    LiteralSize,
    RadixThemesComponent,
)

LiteralCheckboxSize = Literal["1", "2", "3"]
LiteralCheckboxVariant = Literal["classic", "surface", "soft"]


class Checkbox(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Checkbox"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Checkbox size "1" - "3"
    size: Var[LiteralCheckboxSize]

    # Variant of checkbox: "classic" | "surface" | "soft"
    variant: Var[LiteralCheckboxVariant]

    # Override theme color for checkbox
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the checkbox with higher contrast color against background
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


class HighLevelCheckbox(RadixThemesComponent):
    """A checkbox component with a label."""

    tag = "Checkbox"

    # The text label for the checkbox.
    text: Var[str]

    # The gap between the checkbox and the label.
    spacing: Var[LiteralSize]

    # The size of the checkbox "1" - "3".
    size: Var[LiteralCheckboxSize]

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Variant of checkbox: "classic" | "surface" | "soft"
    variant: Var[LiteralCheckboxVariant]

    # Override theme color for checkbox
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the checkbox with higher contrast color against background
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

    @classmethod
    def create(cls, text: Var[str] = Var.create_safe(""), **props) -> Component:
        """Create a checkbox with a label.

        Args:
            text: The text of the label.
            **props: Additional properties to apply to the checkbox item.

        Returns:
            The checkbox component with a label.
        """
        spacing = props.pop("spacing", "2")
        size = props.pop("size", "2")

        return Text.create(
            Flex.create(
                Checkbox.create(
                    size=size,
                    **props,
                ),
                text,
                spacing=spacing,
                **props,
            ),
            as_="label",
            size=size,
        )


class CheckboxNamespace(SimpleNamespace):
    """Checkbox components namespace."""

    __call__ = staticmethod(HighLevelCheckbox.create)


checkbox = CheckboxNamespace()
