"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal, Optional

from reflex.components.component import Component, ComponentNamespace
from reflex.components.radix.themes.layout.flex import Flex
from reflex.components.radix.themes.typography.text import Text
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    LiteralSpacing,
    RadixThemesComponent,
)

LiteralCheckboxSize = Literal["1", "2", "3"]
LiteralCheckboxVariant = Literal["classic", "surface", "soft"]


class Checkbox(RadixThemesComponent):
    """Selects a single value, typically for submission in a form."""

    tag = "Checkbox"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Optional[Var[bool]] = None

    # Checkbox size "1" - "3"
    size: Optional[Var[LiteralCheckboxSize]] = None

    # Variant of checkbox: "classic" | "surface" | "soft"
    variant: Optional[Var[LiteralCheckboxVariant]] = None

    # Override theme color for checkbox
    color_scheme: Optional[Var[LiteralAccentColor]] = None

    # Whether to render the checkbox with higher contrast color against background
    high_contrast: Optional[Var[bool]] = None

    # Whether the checkbox is checked by default
    default_checked: Optional[Var[bool]] = None

    # Whether the checkbox is checked
    checked: Optional[Var[bool]] = None

    # Whether the checkbox is disabled
    disabled: Optional[Var[bool]] = None

    # Whether the checkbox is required
    required: Optional[Var[bool]] = None

    # The name of the checkbox control when submitting the form.
    name: Optional[Var[str]] = None

    # The value of the checkbox control when submitting the form.
    value: Optional[Var[str]] = None

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
    text: Optional[Var[str]] = None

    # The gap between the checkbox and the label.
    spacing: Optional[Var[LiteralSpacing]] = None

    # The size of the checkbox "1" - "3".
    size: Optional[Var[LiteralCheckboxSize]] = None

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Optional[Var[bool]] = None

    # Variant of checkbox: "classic" | "surface" | "soft"
    variant: Optional[Var[LiteralCheckboxVariant]] = None

    # Override theme color for checkbox
    color_scheme: Optional[Var[LiteralAccentColor]] = None

    # Whether to render the checkbox with higher contrast color against background
    high_contrast: Optional[Var[bool]] = None

    # Whether the checkbox is checked by default
    default_checked: Optional[Var[bool]] = None

    # Whether the checkbox is checked
    checked: Optional[Var[bool]] = None

    # Whether the checkbox is disabled
    disabled: Optional[Var[bool]] = None

    # Whether the checkbox is required
    required: Optional[Var[bool]] = None

    # The name of the checkbox control when submitting the form.
    name: Optional[Var[str]] = None

    # The value of the checkbox control when submitting the form.
    value: Optional[Var[str]] = None

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
        flex_props = {}
        if "gap" in props:
            flex_props["gap"] = props.pop("gap", None)

        return Text.create(
            Flex.create(
                Checkbox.create(
                    size=size,
                    **props,
                ),
                text,
                spacing=spacing,
                **flex_props,
            ),
            as_="label",
            size=size,
        )


class CheckboxNamespace(ComponentNamespace):
    """Checkbox components namespace."""

    __call__ = staticmethod(HighLevelCheckbox.create)


checkbox = CheckboxNamespace()
