"""A pin input component."""

from typing import Set

from pynecone.components.component import Component
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class PinInput(ChakraComponent):
    """The component that provides context to all the pin-input fields."""

    tag = "PinInput"

    # State var to bind the the input.
    value: Var[str]

    # If true, the pin input receives focus on mount
    auto_focus: Var[bool]

    # The default value of the pin input
    default_value: Var[str]

    # The border color when the input is invalid.
    error_border_color: Var[str]

    # The border color when the input is focused.
    focus_border_color: Var[str]

    # The top-level id string that will be applied to the input fields. The index of the input will be appended to this top-level id.
    id_: Var[str]

    # The length of the number input.
    length: Var[int]

    # If true, the pin input component is put in the disabled state
    is_disabled: Var[bool]

    # If true, the pin input component is put in the invalid state
    is_invalid: Var[bool]

    # If true, focus will move automatically to the next input once filled
    manage_focus: Var[bool]

    # If true, the input's value will be masked just like `type=password`
    mask: Var[bool]

    # The placeholder for the pin input
    placeholder: Var[str]

    # The type of values the pin-input should allow ("number" | "alphanumeric").
    type_: Var[str]

    # "outline" | "flushed" | "filled" | "unstyled"
    variant: Var[str]

    @classmethod
    def get_controlled_triggers(cls) -> Set[str]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            The controlled event triggers.
        """
        return {"on_change", "on_complete"}

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a pin input component.

        If no children are passed in, the component will create a default pin input
        based on the length prop.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The pin input component.
        """
        if len(children) == 0 and "length" in props:
            children = [PinInputField()] * props["length"]
        return super().create(*children, **props)


class PinInputField(ChakraComponent):
    """The text field that user types in - must be a direct child of PinInput."""

    tag = "PinInputField"
