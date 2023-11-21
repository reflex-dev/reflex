"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal

from reflex.components import el
from reflex.components.component import Component
from reflex.components.forms.debounce import DebounceInput
from reflex.constants import EventTriggers
from reflex.vars import Var

from .base import (
    CommonMarginProps,
    LiteralAccentColor,
    LiteralRadius,
    LiteralSize,
    LiteralVariant,
    RadixThemesComponent,
)

LiteralButtonSize = Literal["1", "2", "3", "4"]


class Button(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Button"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Button size "1" - "4"
    size: Var[LiteralButtonSize]

    # Variant of button: "solid" | "soft" | "outline" | "ghost"
    variant: Var[LiteralVariant]

    # Override theme color for button
    color: Var[LiteralAccentColor]

    # Whether to render the button with higher contrast color against background
    high_contrast: Var[bool]

    # Override theme radius for button: "none" | "small" | "medium" | "large" | "full"
    radius: Var[LiteralRadius]


LiteralSwitchSize = Literal["1", "2", "3", "4"]


class Switch(CommonMarginProps, RadixThemesComponent):
    """A toggle switch alternative to the checkbox."""

    tag = "Switch"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Whether the switch is checked by default
    default_checked: Var[bool]

    # Whether the switch is checked
    checked: Var[bool]

    # If true, prevent the user from interacting with the switch
    disabled: Var[bool]

    # If true, the user must interact with the switch to submit the form
    required: Var[bool]

    # The name of the switch (when submitting a form)
    name: Var[str]

    # The value associated with the "on" position
    value: Var[str]

    # Switch size "1" - "4"
    size: Var[LiteralSwitchSize]

    # Variant of switch: "solid" | "soft" | "outline" | "ghost"
    variant: Var[LiteralVariant]

    # Override theme color for switch
    color: Var[LiteralAccentColor]

    # Whether to render the switch with higher contrast color against background
    high_contrast: Var[bool]

    # Override theme radius for switch: "none" | "small" | "medium" | "large" | "full"
    radius: Var[LiteralRadius]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger name to the argspec passed to the handler.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_CHECKED_CHANGE: lambda checked: [checked],
        }


LiteralTextFieldSize = Literal["1", "2", "3"]
LiteralTextFieldVariant = Literal["classic", "surface", "soft"]


class TextFieldRoot(CommonMarginProps, RadixThemesComponent):
    """Captures user input with an optional slot for buttons and icons."""

    tag = "TextField.Root"

    # Text field size "1" - "3"
    size: Var[LiteralTextFieldSize]

    # Variant of text field: "classic" | "surface" | "soft"
    variant: Var[LiteralTextFieldVariant]

    # Override theme color for text field
    color: Var[LiteralAccentColor]

    # Override theme radius for text field: "none" | "small" | "medium" | "large" | "full"
    radius: Var[LiteralRadius]


class TextField(TextFieldRoot, el.Input):
    """The input part of a TextField, may be used by itself."""

    tag = "TextField.Input"

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an Input component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The component.
        """
        if (
            isinstance(props.get("value"), Var) and props.get("on_change")
        ) or "debounce_timeout" in props:
            # Currently default to 50ms, which appears to be a good balance
            debounce_timeout = props.pop("debounce_timeout", 50)
            # create a debounced input if the user requests full control to avoid typing jank
            return DebounceInput.create(
                super().create(*children, **props), debounce_timeout=debounce_timeout
            )
        return super().create(*children, **props)

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
    color: Var[LiteralAccentColor]

    # Override the gap spacing between slot and input: "1" - "9"
    gap: Var[LiteralSize]
