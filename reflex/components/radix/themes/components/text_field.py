"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal, Optional

from reflex.components import el
from reflex.components.component import Component, ComponentNamespace
from reflex.components.core.debounce import DebounceInput
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    LiteralRadius,
    RadixThemesComponent,
)

LiteralTextFieldSize = Literal["1", "2", "3"]
LiteralTextFieldVariant = Literal["classic", "surface", "soft"]


class TextFieldRoot(el.Div, RadixThemesComponent):
    """Captures user input with an optional slot for buttons and icons."""

    tag: str = "TextField.Root"

    # Text field size "1" - "3"
    size: Optional[Var[LiteralTextFieldSize]] = None

    # Variant of text field: "classic" | "surface" | "soft"
    variant: Optional[Var[LiteralTextFieldVariant]] = None

    # Override theme color for text field
    color_scheme: Optional[Var[LiteralAccentColor]] = None

    # Override theme radius for text field: "none" | "small" | "medium" | "large" | "full"
    radius: Optional[Var[LiteralRadius]] = None


class TextFieldInput(el.Input, TextFieldRoot):
    """The input part of a TextField, may be used by itself."""

    tag: str = "TextField.Input"

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an Input component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The component.
        """
        if props.get("value") is not None and props.get("on_change"):
            # create a debounced input if the user requests full control to avoid typing jank
            return DebounceInput.create(super().create(*children, **props))
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

    tag: str = "TextField.Slot"

    # Override theme color for text field slot
    color_scheme: Optional[Var[LiteralAccentColor]] = None


class Input(RadixThemesComponent):
    """High level wrapper for the Input component."""

    # Text field size "1" - "3"
    size: Optional[Var[LiteralTextFieldSize]] = None

    # Variant of text field: "classic" | "surface" | "soft"
    variant: Optional[Var[LiteralTextFieldVariant]] = None

    # Override theme color for text field
    color_scheme: Optional[Var[LiteralAccentColor]] = None

    # Override theme radius for text field: "none" | "small" | "medium" | "large" | "full"
    radius: Optional[Var[LiteralRadius]] = None

    # Whether the input should have autocomplete enabled
    auto_complete: Optional[Var[bool]] = None

    # The value of the input when initially rendered.
    default_value: Optional[Var[str]] = None

    # Disables the input
    disabled: Optional[Var[bool]] = None

    # Specifies the maximum number of characters allowed in the input
    max_length: Optional[Var[str]] = None

    # Specifies the minimum number of characters required in the input
    min_length: Optional[Var[str]] = None

    # Name of the input, used when sending form data
    name: Optional[Var[str]] = None

    # Placeholder text in the input
    placeholder: Optional[Var[str]] = None

    # Indicates whether the input is read-only
    read_only: Optional[Var[bool]] = None

    # Indicates that the input is required
    required: Optional[Var[bool]] = None

    # Specifies the type of input
    type: Optional[Var[str]] = None

    # Value of the input
    value: Optional[Var[str]] = None

    @classmethod
    def create(cls, **props):
        """Create an Input component.

        Args:
            **props: The properties of the component.

        Returns:
            The component.
        """
        return TextFieldInput.create(**props)

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


class TextField(ComponentNamespace):
    """TextField components namespace."""

    root = staticmethod(TextFieldRoot.create)
    input = staticmethod(TextFieldInput.create)
    slot = staticmethod(TextFieldSlot.create)
    __call__ = staticmethod(Input.create)


text_field = TextField()
