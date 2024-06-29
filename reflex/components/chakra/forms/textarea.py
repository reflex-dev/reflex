"""A textarea component."""

from __future__ import annotations

from reflex.components.chakra import ChakraComponent, LiteralInputVariant
from reflex.components.component import Component
from reflex.components.core.debounce import DebounceInput
from reflex.event import EventHandler
from reflex.vars import Var


class TextArea(ChakraComponent):
    """A text area component."""

    tag = "Textarea"

    # State var to bind the input.
    value: Var[str]

    # The default value of the textarea.
    default_value: Var[str]

    # The placeholder text.
    placeholder: Var[str]

    # The border color when the input is invalid.
    error_border_color: Var[str]

    # The border color when the input is focused.
    focus_border_color: Var[str]

    # If true, the form control will be disabled.
    is_disabled: Var[bool]

    # If true, the form control will be invalid.
    is_invalid: Var[bool]

    # If true, the form control will be read-only.
    is_read_only: Var[bool]

    # If true, the form control will be required.
    is_required: Var[bool]

    # "outline" | "filled" | "flushed" | "unstyled"
    variant: Var[LiteralInputVariant]

    # The name of the form field
    name: Var[str]

    # Fired when the value changes.
    on_change: EventHandler[lambda e0: [e0.target.value]]

    # Fired when the textarea gets focus.
    on_focus: EventHandler[lambda e0: [e0.target.value]]

    # Fired when the textarea loses focus.
    on_blur: EventHandler[lambda e0: [e0.target.value]]

    # Fired when a key is pressed down.
    on_key_down: EventHandler[lambda e0: [e0.key]]

    # Fired when a key is released.
    on_key_up: EventHandler[lambda e0: [e0.key]]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an Input component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The component.
        """
        if props.get("value") is not None and props.get("on_change") is not None:
            # create a debounced input if the user requests full control to avoid typing jank
            return DebounceInput.create(super().create(*children, **props))
        return super().create(*children, **props)
