"""A number input component."""
from numbers import Number
from typing import Any, Dict, Optional

from reflex.components.chakra import (
    ChakraComponent,
    LiteralButtonSize,
    LiteralInputVariant,
)
from reflex.components.component import Component
from reflex.constants import EventTriggers
from reflex.vars import Var


class NumberInput(ChakraComponent):
    """The wrapper that provides context and logic to the components."""

    tag: str = "NumberInput"

    # State var to bind the input.
    value: Optional[Var[Number]] = None

    # If true, the input's value will change based on mouse wheel.
    allow_mouse_wheel: Optional[Var[bool]] = None

    # This controls the value update when you blur out of the input. - If true and the value is greater than max, the value will be reset to max - Else, the value remains the same.
    clamped_value_on_blur: Optional[Var[bool]] = None

    # The initial value of the counter. Should be less than max and greater than min
    default_value: Optional[Var[Number]] = None

    # The border color when the input is invalid.
    error_border_color: Optional[Var[str]] = None

    # The border color when the input is focused.
    focus_border_color: Optional[Var[str]] = None

    # If true, the input will be focused as you increment or decrement the value with the stepper
    focus_input_on_change: Optional[Var[bool]] = None

    # Hints at the type of data that might be entered by the user. It also determines the type of keyboard shown to the user on mobile devices ("text" | "search" | "none" | "tel" | "url" | "email" | "numeric" | "decimal")
    # input_mode: Optional[Var[LiteralInputNumberMode]] = None

    # Whether the input should be disabled.
    is_disabled: Optional[Var[bool]] = None

    # If true, the input will have `aria-invalid` set to true
    is_invalid: Optional[Var[bool]] = None

    # If true, the input will be in readonly mode
    is_read_only: Optional[Var[bool]] = None

    # Whether the input is required
    is_required: Optional[Var[bool]] = None

    # Whether the pressed key should be allowed in the input. The default behavior is to allow DOM floating point characters defined by /^[Ee0-9+\-.]$/
    is_valid_character: Optional[Var[str]] = None

    # This controls the value update behavior in general. - If true and you use the stepper or up/down arrow keys, the value will not exceed the max or go lower than min - If false, the value will be allowed to go out of range.
    keep_within_range: Optional[Var[bool]] = None

    # The maximum value of the counter
    max_: Optional[Var[Number]] = None

    # The minimum value of the counter
    min_: Optional[Var[Number]] = None

    # "outline" | "filled" | "flushed" | "unstyled"
    variant: Optional[Var[LiteralInputVariant]] = None

    # "lg" | "md" | "sm" | "xs"
    size: Optional[Var[LiteralButtonSize]] = None

    # The name of the form field
    name: Optional[Var[str]] = None

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_CHANGE: lambda e0: [e0],
        }

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
            _id = props.pop("id", None)
            children = [
                NumberInputField.create(id=_id)
                if _id is not None
                else NumberInputField.create(),
                NumberInputStepper.create(
                    NumberIncrementStepper.create(),
                    NumberDecrementStepper.create(),
                ),
            ]
        return super().create(*children, **props)


class NumberInputField(ChakraComponent):
    """The input field itself."""

    tag: str = "NumberInputField"


class NumberInputStepper(ChakraComponent):
    """The wrapper for the input's stepper buttons."""

    tag: str = "NumberInputStepper"


class NumberIncrementStepper(ChakraComponent):
    """The button to increment the value of the input."""

    tag: str = "NumberIncrementStepper"


class NumberDecrementStepper(ChakraComponent):
    """The button to decrement the value of the input."""

    tag: str = "NumberDecrementStepper"
