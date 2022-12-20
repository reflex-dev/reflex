"""An input component."""

from typing import Set

from pynecone.components.component import EVENT_ARG
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Input(ChakraComponent):
    """The Input component is a component that is used to get user input in a text field."""

    tag = "Input"

    # State var to bind the the input.
    value: Var[str]

    # The default value of the input.
    default_value: Var[str]

    # The placeholder text.
    placeholder: Var[str]

    # The type of input.
    type_: Var[str] = "text"  # type: ignore

    # The border color when the input is invalid.
    error_border_color: Var[str]

    # The border color when the input is focused.
    focus_border_color: Var[str]

    # If true, the form control will be disabled. This has 2 side effects - The FormLabel will have `data-disabled` attribute - The form element (e.g, Input) will be disabled
    is_disabled: Var[bool]

    # If true, the form control will be invalid. This has 2 side effects - The FormLabel and FormErrorIcon will have `data-invalid` set to true - The form element (e.g, Input) will have `aria-invalid` set to true
    is_invalid: Var[bool]

    # If true, the form control will be readonly.
    is_read_only: Var[bool]

    # If true, the form control will be required. This has 2 side effects - The FormLabel will show a required indicator - The form element (e.g, Input) will have `aria-required` set to true
    is_required: Var[bool]

    # "outline" | "filled" | "flushed" | "unstyled"
    variant: Var[str]

    # "lg" | "md" | "sm" | "xs"
    size: Var[str]

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


class InputGroup(ChakraComponent):
    """The InputGroup component is a component that is used to group a set of inputs."""

    tag = "InputGroup"


class InputLeftAddon(ChakraComponent):
    """The InputLeftAddon component is a component that is used to add an addon to the left of an input."""

    tag = "InputLeftAddon"


class InputRightAddon(ChakraComponent):
    """The InputRightAddon component is a component that is used to add an addon to the right of an input."""

    tag = "InputRightAddon"
