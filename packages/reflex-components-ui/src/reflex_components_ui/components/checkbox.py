"""A checkbox: a native input, drawn as Radix Themes draws its own."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.components.tags import CommonTag
from reflex_base.event import EventHandler, checked_input_event
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_ui.base import UIComponent
from reflex_components_ui.layout.flex import Flex
from reflex_components_ui.props import LiteralSpacing
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.checkbox import CHECKBOX
from reflex_components_ui.themes import LiteralAccentColor
from reflex_components_ui.typography.text import Text

LiteralCheckboxSize = Literal["1", "2", "3"]
LiteralCheckboxVariant = Literal["classic", "surface", "soft"]


class CheckedInput(UIComponent):
    """A native input that is checked or not: a checkbox, a switch."""

    tag = "input"

    # The type of the input.
    _type: ClassVar[str] = "checkbox"

    def _set_slot(self) -> None:
        """Render the input itself: it has no child to be rendered as."""

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the input with its type.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag. An input whose ``checked`` nothing changes says so, as
            React asks of an input it controls.
        """
        tag = super()._render(props).add_props(type=self._type)
        if (
            getattr(self, "checked", None) is not None
            and "on_change" not in self.event_triggers
        ):
            return tag.add_props(read_only=True)
        return tag


class Checkbox(CheckedInput):
    """Selects a single value, typically for submission in a form."""

    styles: ClassVar[ComponentStyles] = CHECKBOX

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

    on_change: EventHandler[checked_input_event] = field(
        doc="Fired when the checkbox is checked or unchecked."
    )


class HighLevelCheckbox(Checkbox):
    """A checkbox component with a label."""

    text: Var[str] = field(doc="The text label for the checkbox.")

    spacing: Var[LiteralSpacing] = field(
        doc="The gap between the checkbox and the label."
    )

    size: Var[LiteralCheckboxSize] = field(doc='The size of the checkbox "1" - "3".')

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
                Checkbox.create(size=size, **props),
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
