"""A textarea component."""

from typing import Set

from pynecone.components.component import EVENT_ARG
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class TextArea(ChakraComponent):
    """A text area component."""

    tag = "Textarea"

    # State var to bind the the input.
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

    # If true, the form control will be readonly.
    is_read_only: Var[bool]

    # If true, the form control will be required.
    is_required: Var[bool]

    # "outline" | "filled" | "flushed" | "unstyled"
    variant: Var[str]

    @classmethod
    def get_controlled_triggers(cls) -> Set[str]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            The controlled event triggers.
        """
        return {"on_change", "on_focus", "on_blur"}

    @classmethod
    def get_controlled_value(cls) -> Var:
        """Get the var that is passed to the event handler for controlled triggers.

        Returns:
            The controlled value.
        """
        return EVENT_ARG.target.value
