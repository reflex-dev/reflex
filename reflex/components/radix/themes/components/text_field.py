"""Interactive components provided by @radix-ui/themes."""

from __future__ import annotations

from typing import Literal, Union

from reflex.components.component import Component, ComponentNamespace
from reflex.components.core.breakpoints import Responsive
from reflex.components.core.debounce import DebounceInput
from reflex.components.el import elements
from reflex.event import EventHandler, input_event, key_event
from reflex.utils.types import is_optional
from reflex.vars.base import Var
from reflex.vars.number import ternary_operation

from ..base import LiteralAccentColor, LiteralRadius, RadixThemesComponent

LiteralTextFieldSize = Literal["1", "2", "3"]
LiteralTextFieldVariant = Literal["classic", "surface", "soft"]


class TextFieldRoot(elements.Input, RadixThemesComponent):
    """Captures user input with an optional slot for buttons and icons."""

    tag = "TextField.Root"

    # Text field size "1" - "3"
    size: Var[Responsive[LiteralTextFieldSize]]

    # Variant of text field: "classic" | "surface" | "soft"
    variant: Var[LiteralTextFieldVariant]

    # Override theme color for text field
    color_scheme: Var[LiteralAccentColor]

    # Override theme radius for text field: "none" | "small" | "medium" | "large" | "full"
    radius: Var[LiteralRadius]

    # Whether the input should have autocomplete enabled
    auto_complete: Var[bool]

    # The value of the input when initially rendered.
    default_value: Var[str]

    # Disables the input
    disabled: Var[bool]

    # Specifies the maximum number of characters allowed in the input
    max_length: Var[int]

    # Specifies the minimum number of characters required in the input
    min_length: Var[int]

    # Name of the input, used when sending form data
    name: Var[str]

    # Placeholder text in the input
    placeholder: Var[str]

    # Indicates whether the input is read-only
    read_only: Var[bool]

    # Indicates that the input is required
    required: Var[bool]

    # Specifies the type of input
    type: Var[str]

    # Value of the input
    value: Var[Union[str, int, float]]

    # References a datalist for suggested options
    list: Var[str]

    # Fired when the value of the textarea changes.
    on_change: EventHandler[input_event]

    # Fired when the textarea is focused.
    on_focus: EventHandler[input_event]

    # Fired when the textarea is blurred.
    on_blur: EventHandler[input_event]

    # Fired when a key is pressed down.
    on_key_down: EventHandler[key_event]

    # Fired when a key is released.
    on_key_up: EventHandler[key_event]

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
            props["value"] = ternary_operation(
                (value_var != Var.create(None))  # pyright: ignore [reportArgumentType]
                & (value_var != Var(_js_expr="undefined")),
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

    # Override theme color for text field slot
    color_scheme: Var[LiteralAccentColor]


class TextField(ComponentNamespace):
    """TextField components namespace."""

    slot = staticmethod(TextFieldSlot.create)
    __call__ = staticmethod(TextFieldRoot.create)


input = text_field = TextField()
