"""A textarea component."""
from __future__ import annotations

from typing import Any, Optional, Union

from reflex.components.chakra import ChakraComponent, LiteralInputVariant
from reflex.components.component import Component
from reflex.components.core.debounce import DebounceInput
from reflex.constants import EventTriggers
from reflex.vars import Var


class TextArea(ChakraComponent):
    """A text area component."""

    tag: str = "Textarea"

    # State var to bind the input.
    value: Optional[Var[str]] = None

    # The default value of the textarea.
    default_value: Optional[Var[str]] = None

    # The placeholder text.
    placeholder: Optional[Var[str]] = None

    # The border color when the input is invalid.
    error_border_color: Optional[Var[str]] = None

    # The border color when the input is focused.
    focus_border_color: Optional[Var[str]] = None

    # If true, the form control will be disabled.
    is_disabled: Optional[Var[bool]] = None

    # If true, the form control will be invalid.
    is_invalid: Optional[Var[bool]] = None

    # If true, the form control will be read-only.
    is_read_only: Optional[Var[bool]] = None

    # If true, the form control will be required.
    is_required: Optional[Var[bool]] = None

    # "outline" | "filled" | "flushed" | "unstyled"
    variant: Optional[Var[LiteralInputVariant]] = None

    # The name of the form field
    name: Optional[Var[str]] = None

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
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
