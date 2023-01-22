"""A number input component."""

from typing import Set

from pynecone.components.component import Component
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class NumberInput(ChakraComponent):
    """The wrapper that provides context and logic to the components."""

    tag = "NumberInput"

    # State var to bind the the input.
    value: Var[int]

    # If true, the input's value will change based on mouse wheel.
    allow_mouse_wheel: Var[bool]

    # This controls the value update when you blur out of the input. - If true and the value is greater than max, the value will be reset to max - Else, the value remains the same.
    clamped_value_on_blur: Var[bool]

    # The initial value of the counter. Should be less than max and greater than min
    default_value: Var[int]

    # The border color when the input is invalid.
    error_border_color: Var[str]

    # The border color when the input is focused.
    focus_border_color: Var[str]

    # If true, the input will be focused as you increment or decrement the value with the stepper
    focus_input_on_change: Var[bool]

    # Hints at the type of data that might be entered by the user. It also determines the type of keyboard shown to the user on mobile devices ("text" | "search" | "none" | "tel" | "url" | "email" | "numeric" | "decimal")
    input_mode: Var[str]

    # Whether the input should be disabled.
    is_disabled: Var[bool]

    # If true, the input will have `aria-invalid` set to true
    is_invalid: Var[bool]

    # If true, the input will be in readonly mode
    is_read_only: Var[bool]

    # Whether the input is required
    is_required: Var[bool]

    # Whether the pressed key should be allowed in the input. The default behavior is to allow DOM floating point characters defined by /^[Ee0-9+\-.]$/
    is_valid_character: Var[str]

    # This controls the value update behavior in general. - If true and you use the stepper or up/down arrow keys, the value will not exceed the max or go lower than min - If false, the value will be allowed to go out of range.
    keep_within_range: Var[bool]

    # The maximum value of the counter
    max_: Var[int]

    # The minimum value of the counter
    min_: Var[int]

    # "outline" | "filled" | "flushed" | "unstyled"
    variant: Var[str]

    @classmethod
    def get_controlled_triggers(cls) -> Set[str]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            The controlled event triggers.
        """
        return {"on_change"}

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a number input component.

        If no children are provided, a default stepper will be used.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The component.
        """
        if len(children) == 0:
            children = [
                NumberInputField.create(),
                NumberInputStepper.create(
                    NumberIncrementStepper.create(),
                    NumberDecrementStepper.create(),
                ),
            ]
        return super().create(*children, **props)


class NumberInputField(ChakraComponent):
    """The input field itself."""

    tag = "NumberInputField"


class NumberInputStepper(ChakraComponent):
    """The wrapper for the input's stepper buttons."""

    tag = "NumberInputStepper"


class NumberIncrementStepper(ChakraComponent):
    """The button to increment the value of the input."""

    tag = "NumberIncrementStepper"


class NumberDecrementStepper(ChakraComponent):
    """The button to decrement the value of the input."""

    tag = "NumberDecrementStepper"
