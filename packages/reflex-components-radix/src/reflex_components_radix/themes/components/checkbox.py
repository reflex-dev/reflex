"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.event import EventHandler, passthrough_event_spec
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import (
    LiteralAccentColor,
    LiteralSpacing,
    RadixThemesComponent,
)
from reflex_components_radix.themes.layout.flex import Flex
from reflex_components_radix.themes.typography.text import Text

LiteralCheckboxSize = Literal["1", "2", "3"]
LiteralCheckboxVariant = Literal["classic", "surface", "soft"]


class Checkbox(RadixThemesComponent):
    """Selects a single value, typically for submission in a form."""

    tag = "Checkbox"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

    size: Var[Responsive[LiteralCheckboxSize]] = field(doc='Checkbox size "1" - "3"')

    variant: Var[LiteralCheckboxVariant] = field(
        doc='Variant of checkbox: "classic" | "surface" | "soft"'
    )

    color_scheme: Var[LiteralAccentColor] = field(
        doc="Override theme color for checkbox"
    )

    high_contrast: Var[bool] = field(
        doc="Whether to render the checkbox with higher contrast color against background"
    )

    default_checked: Var[bool] = field(doc="Whether the checkbox is checked by default")

    checked: Var[bool] = field(doc="Whether the checkbox is checked")

    disabled: Var[bool] = field(doc="Whether the checkbox is disabled")

    required: Var[bool] = field(doc="Whether the checkbox is required")

    name: Var[str] = field(
        doc="The name of the checkbox control when submitting the form."
    )

    value: Var[str] = field(
        doc="The value of the checkbox control when submitting the form."
    )

    # Props to rename
    _rename_props = {"onChange": "onCheckedChange"}

    on_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when the checkbox is checked or unchecked."
    )


class HighLevelCheckbox(RadixThemesComponent):
    """A checkbox component with a label."""

    tag = "Checkbox"

    text: Var[str] = field(doc="The text label for the checkbox.")

    spacing: Var[LiteralSpacing] = field(
        doc="The gap between the checkbox and the label."
    )

    size: Var[LiteralCheckboxSize] = field(doc='The size of the checkbox "1" - "3".')

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

    variant: Var[LiteralCheckboxVariant] = field(
        doc='Variant of checkbox: "classic" | "surface" | "soft"'
    )

    color_scheme: Var[LiteralAccentColor] = field(
        doc="Override theme color for checkbox"
    )

    high_contrast: Var[bool] = field(
        doc="Whether to render the checkbox with higher contrast color against background"
    )

    default_checked: Var[bool] = field(doc="Whether the checkbox is checked by default")

    checked: Var[bool] = field(doc="Whether the checkbox is checked")

    disabled: Var[bool] = field(doc="Whether the checkbox is disabled")

    required: Var[bool] = field(doc="Whether the checkbox is required")

    name: Var[str] = field(
        doc="The name of the checkbox control when submitting the form."
    )

    value: Var[str] = field(
        doc="The value of the checkbox control when submitting the form."
    )

    # Props to rename
    _rename_props = {"onChange": "onCheckedChange"}

    on_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc="Fired when the checkbox is checked or unchecked."
    )

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
