"""A textarea component."""

from typing import Dict

from reflex.components.component import EVENT_ARG, Component
from reflex.components.libs.chakra import ChakraComponent
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
    variant: Var[str]

    def get_controlled_triggers(self) -> Dict[str, Var]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            "on_change": EVENT_ARG.target.value,
            "on_focus": EVENT_ARG.target.value,
            "on_blur": EVENT_ARG.target.value,
            "on_key_down": EVENT_ARG.key,
            "on_key_up": EVENT_ARG.key,
        }

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an Input component.

        Args:
            children: The children of the component.
            props: The properties of the component.

        Returns:
            The component.

        Raises:
            ValueError: If the value is a state Var.
        """
        if isinstance(props.get("value"), Var) and props.get("on_change"):
            raise ValueError(
                "TextArea value cannot be bound to a state Var with on_change handler.\n"
                "Provide value prop to rx.debounce_input with rx.text_area as a child "
                "component to create a fully controlled input."
            )
        return super().create(*children, **props)
