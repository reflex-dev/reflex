"""Interactive components provided by @radix-ui/themes."""
from __future__ import annotations

from typing import Any, Dict, Literal, Union

from reflex.components.base.fragment import Fragment
from reflex.components.component import Component, ComponentNamespace
from reflex.components.core.debounce import DebounceInput
from reflex.components.el import elements
from reflex.constants import EventTriggers
from reflex.style import Style, format_as_emotion
from reflex.utils import console
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    LiteralRadius,
    RadixThemesComponent,
)

LiteralTextFieldSize = Literal["1", "2", "3"]
LiteralTextFieldVariant = Literal["classic", "surface", "soft"]


class TextFieldRoot(elements.Div, RadixThemesComponent):
    """Captures user input with an optional slot for buttons and icons."""

    tag = "TextField.Root"

    # Text field size "1" - "3"
    size: Var[LiteralTextFieldSize]

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

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an Input component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The component.
        """
        component = super().create(*children, **props)
        if props.get("value") is not None and props.get("on_change"):
            # create a debounced input if the user requests full control to avoid typing jank
            return DebounceInput.create(component)
        return component

    @classmethod
    def create_root_deprecated(cls, *children, **props) -> Component:
        """Create a Fragment component (wrapper for deprecated name).

        Copy the attributes that were previously defined on TextFieldRoot in 0.4.9 to
        any child input elements (via custom_attrs).

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The component.
        """
        console.deprecate(
            feature_name="rx.input.root",
            reason="use rx.input without the .root suffix",
            deprecation_version="0.5.0",
            removal_version="0.6.0",
        )
        inputs = [
            child
            for child in children
            if isinstance(child, (TextFieldRoot, DebounceInput))
        ]
        if not inputs:
            # Old-style where no explicit child input was provided
            return cls.create(*children, **props)
        slots = [child for child in children if isinstance(child, TextFieldSlot)]
        carry_props = {
            prop: props.pop(prop)
            for prop in ["size", "variant", "color_scheme", "radius"]
            if prop in props
        }
        template = cls.create(**props)
        for child in inputs:
            child.children.extend(slots)
            custom_attrs = child.custom_attrs
            custom_attrs.update(
                {
                    prop: value
                    for prop, value in carry_props.items()
                    if prop not in custom_attrs and getattr(child, prop) is None
                }
            )
            style = Style(template.style)
            style.update(child.style)
            child._get_style = lambda style=style: {
                "css": Var.create(format_as_emotion(style))
            }
            for trigger in template.event_triggers:
                if trigger not in child.event_triggers:
                    child.event_triggers[trigger] = template.event_triggers[trigger]
        return Fragment.create(*inputs)

    @classmethod
    def create_input_deprecated(cls, *children, **props) -> Component:
        """Create a TextFieldRoot component (wrapper for deprecated name).

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The component.
        """
        console.deprecate(
            feature_name="rx.input.input",
            reason="use rx.input without the .input suffix",
            deprecation_version="0.5.0",
            removal_version="0.6.0",
        )
        return cls.create(*children, **props)

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_CHANGE: lambda e0: [e0.target.value],
            EventTriggers.ON_FOCUS: lambda e0: [e0.target.value],
            EventTriggers.ON_BLUR: lambda e0: [e0.target.value],
            EventTriggers.ON_KEY_DOWN: lambda e0: [e0.key],
            EventTriggers.ON_KEY_UP: lambda e0: [e0.key],
        }


class TextFieldSlot(RadixThemesComponent):
    """Contains icons or buttons associated with an Input."""

    tag = "TextField.Slot"

    # Override theme color for text field slot
    color_scheme: Var[LiteralAccentColor]


class TextField(ComponentNamespace):
    """TextField components namespace."""

    root = staticmethod(TextFieldRoot.create_root_deprecated)
    input = staticmethod(TextFieldRoot.create_input_deprecated)
    slot = staticmethod(TextFieldSlot.create)
    __call__ = staticmethod(TextFieldRoot.create)


input = text_field = TextField()
