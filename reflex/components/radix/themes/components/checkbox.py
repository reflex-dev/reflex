"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex.components.component import Component, ComponentNamespace
from reflex.components.core.breakpoints import Responsive
from reflex.components.radix.themes.layout.flex import Flex
from reflex.components.radix.themes.typography.text import Text
from reflex.event import EventHandler
from reflex.ivars.base import ImmutableVar, LiteralVar

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
    as_child: ImmutableVar[bool]

    # Checkbox size "1" - "3"
    size: ImmutableVar[Responsive[LiteralCheckboxSize]]

    # Variant of checkbox: "classic" | "surface" | "soft"
    variant: ImmutableVar[LiteralCheckboxVariant]

    # Override theme color for checkbox
    color_scheme: ImmutableVar[LiteralAccentColor]

    # Whether to render the checkbox with higher contrast color against background
    high_contrast: ImmutableVar[bool]

    # Whether the checkbox is checked by default
    default_checked: ImmutableVar[bool]

    # Whether the checkbox is checked
    checked: ImmutableVar[bool]

    # Whether the checkbox is disabled
    disabled: ImmutableVar[bool]

    # Whether the checkbox is required
    required: ImmutableVar[bool]

    # The name of the checkbox control when submitting the form.
    name: ImmutableVar[str]

    # The value of the checkbox control when submitting the form.
    value: ImmutableVar[str]

    # Props to rename
    _rename_props = {"onChange": "onCheckedChange"}

    # Fired when the checkbox is checked or unchecked.
    on_change: EventHandler[lambda e0: [e0]]


class HighLevelCheckbox(RadixThemesComponent):
    """A checkbox component with a label."""

    tag = "Checkbox"

    # The text label for the checkbox.
    text: ImmutableVar[str]

    # The gap between the checkbox and the label.
    spacing: ImmutableVar[LiteralSpacing]

    # The size of the checkbox "1" - "3".
    size: ImmutableVar[LiteralCheckboxSize]

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: ImmutableVar[bool]

    # Variant of checkbox: "classic" | "surface" | "soft"
    variant: ImmutableVar[LiteralCheckboxVariant]

    # Override theme color for checkbox
    color_scheme: ImmutableVar[LiteralAccentColor]

    # Whether to render the checkbox with higher contrast color against background
    high_contrast: ImmutableVar[bool]

    # Whether the checkbox is checked by default
    default_checked: ImmutableVar[bool]

    # Whether the checkbox is checked
    checked: ImmutableVar[bool]

    # Whether the checkbox is disabled
    disabled: ImmutableVar[bool]

    # Whether the checkbox is required
    required: ImmutableVar[bool]

    # The name of the checkbox control when submitting the form.
    name: ImmutableVar[str]

    # The value of the checkbox control when submitting the form.
    value: ImmutableVar[str]

    # Props to rename
    _rename_props = {"onChange": "onCheckedChange"}

    # Fired when the checkbox is checked or unchecked.
    on_change: EventHandler[lambda e0: [e0]]

    @classmethod
    def create(
        cls, text: ImmutableVar[str] = LiteralVar.create(""), **props
    ) -> Component:
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
