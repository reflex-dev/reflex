"""Interactive components provided by @radix-ui/themes."""

from __future__ import annotations

from typing import Literal

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.event import EventHandler, input_event, key_event
from reflex_base.utils.types import is_optional
from reflex_base.vars.base import Var
from reflex_base.vars.number import ternary_operation
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.debounce import DebounceInput
from reflex_components_core.el import elements

from reflex_components_radix.themes.base import (
    LiteralAccentColor,
    LiteralRadius,
    RadixThemesComponent,
)

LiteralTextFieldSize = Literal["1", "2", "3"]
LiteralTextFieldVariant = Literal["classic", "surface", "soft"]


class TextFieldRoot(elements.Input, RadixThemesComponent):
    """Captures user input with an optional slot for buttons and icons."""

    tag = "TextField.Root"

    size: Var[Responsive[LiteralTextFieldSize]] = field(doc='Text field size "1" - "3"')

    variant: Var[LiteralTextFieldVariant] = field(
        doc='Variant of text field: "classic" | "surface" | "soft"'
    )

    color_scheme: Var[LiteralAccentColor] = field(
        doc="Override theme color for text field"
    )

    radius: Var[LiteralRadius] = field(
        doc='Override theme radius for text field: "none" | "small" | "medium" | "large" | "full"'
    )

    auto_complete: Var[bool] = field(
        doc="Whether the input should have autocomplete enabled"
    )

    default_value: Var[str] = field(
        doc="The value of the input when initially rendered."
    )

    disabled: Var[bool] = field(doc="Disables the input")

    max_length: Var[int] = field(
        doc="Specifies the maximum number of characters allowed in the input"
    )

    min_length: Var[int] = field(
        doc="Specifies the minimum number of characters required in the input"
    )

    name: Var[str] = field(doc="Name of the input, used when sending form data")

    placeholder: Var[str] = field(doc="Placeholder text in the input")

    read_only: Var[bool] = field(doc="Indicates whether the input is read-only")

    required: Var[bool] = field(doc="Indicates that the input is required")

    type: Var[str] = field(doc="Specifies the type of input")

    value: Var[str | int | float] = field(doc="Value of the input")

    list: Var[str] = field(doc="References a datalist for suggested options")

    on_change: EventHandler[input_event] = field(
        doc="Fired when the value of the textarea changes."
    )

    on_focus: EventHandler[input_event] = field(
        doc="Fired when the textarea is focused."
    )

    on_blur: EventHandler[input_event] = field(
        doc="Fired when the textarea is blurred."
    )

    on_key_down: EventHandler[key_event] = field(
        doc="Fired when a key is pressed down."
    )

    on_key_up: EventHandler[key_event] = field(doc="Fired when a key is released.")

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an Input component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The component.
        """
        value = props.get("value")

        # React expects an empty string(instead of null) for controlled inputs.
        if value is not None and is_optional(
            (value_var := Var.create(value))._var_type
        ):
            value_var_is_not_none = value_var != Var.create(None)
            value_var_is_not_undefined = value_var != Var(_js_expr="undefined")
            props["value"] = ternary_operation(
                value_var_is_not_none & value_var_is_not_undefined,
                value,
                Var.create(""),
            )

        component = super().create(*children, **props)
        if props.get("value") is not None and props.get("on_change") is not None:
            # create a debounced input if the user requests full control to avoid typing jank
            return DebounceInput.create(component)
        return component


class TextFieldSlot(RadixThemesComponent):
    """Contains icons or buttons associated with an Input."""

    tag = "TextField.Slot"

    color_scheme: Var[LiteralAccentColor] = field(
        doc="Override theme color for text field slot"
    )

    side: Var[Literal["left", "right"]] = field(
        doc="Which side of the input the slot should be placed on"
    )


class TextField(ComponentNamespace):
    """TextField components namespace."""

    slot = staticmethod(TextFieldSlot.create)
    __call__ = staticmethod(TextFieldRoot.create)


input = text_field = TextField()
