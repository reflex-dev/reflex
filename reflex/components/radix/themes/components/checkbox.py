"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex.components.component import Component, ComponentNamespace
from reflex.components.core.breakpoints import Responsive
from reflex.components.radix.themes.base import (
    LiteralAccentColor,
    LiteralSpacing,
    RadixThemesComponent,
)
from reflex.components.radix.themes.layout.flex import Flex
from reflex.components.radix.themes.typography.text import Text
from reflex.event import EventHandler, passthrough_event_spec
from reflex.vars.base import Var

LiteralCheckboxSize = Literal["1", "2", "3"]
LiteralCheckboxVariant = Literal["classic", "surface", "soft"]


class Checkbox(RadixThemesComponent):
    """Selects a single value, typically for submission in a form."""

    tag = "Checkbox"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Checkbox size "1" - "3"
    size: Var[Responsive[LiteralCheckboxSize]]

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

    # Fired when the checkbox is checked or unchecked.
    on_change: EventHandler[passthrough_event_spec(bool)]


class HighLevelCheckbox(RadixThemesComponent):
    """A checkbox component with a label."""

    tag = "Checkbox"

    # The text label for the checkbox.
    text: Var[str]

    # The gap between the checkbox and the label.
    spacing: Var[LiteralSpacing]

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

    # Fired when the checkbox is checked or unchecked.
    on_change: EventHandler[passthrough_event_spec(bool)]

    @classmethod
    def create(cls, text: Var[str] = Var.create(""), **props) -> Component:
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
