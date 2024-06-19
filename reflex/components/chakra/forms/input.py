"""An input component."""

from reflex.components.chakra import (
    ChakraComponent,
    LiteralButtonSize,
    LiteralInputVariant,
)
from reflex.components.component import Component
from reflex.components.core.debounce import DebounceInput
from reflex.components.literals import LiteralInputType
from reflex.constants import MemoizationMode
from reflex.event import EventHandler
from reflex.utils.imports import ImportDict
from reflex.vars import Var


class Input(ChakraComponent):
    """The Input component is a component that is used to get user input in a text field."""

    tag = "Input"

    # State var to bind the input.
    value: Var[str]

    # The default value of the input.
    default_value: Var[str]

    # The placeholder text.
    placeholder: Var[str]

    # The type of input.
    type_: Var[LiteralInputType]

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
    variant: Var[LiteralInputVariant]

    # "lg" | "md" | "sm" | "xs"
    size: Var[LiteralButtonSize]

    # The name of the form field
    name: Var[str]

    # Fired when the input value changes.
    on_change: EventHandler[lambda e0: [e0.target.value]]

    # Fired when the input is focused.
    on_focus: EventHandler[lambda e0: [e0.target.value]]

    # Fired when the input lose focus.
    on_blur: EventHandler[lambda e0: [e0.target.value]]

    # Fired when a key is pressed down.
    on_key_down: EventHandler[lambda e0: [e0.key]]

    # Fired when a key is released.
    on_key_up: EventHandler[lambda e0: [e0.key]]

    def add_imports(self) -> ImportDict:
        """Add imports for the Input component.

        Returns:
            The import dict.
        """
        return {"/utils/state": "set_val"}

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


class InputGroup(ChakraComponent):
    """The InputGroup component is a component that is used to group a set of inputs."""

    tag = "InputGroup"

    _memoization_mode = MemoizationMode(recursive=False)


class InputLeftAddon(ChakraComponent):
    """The InputLeftAddon component is a component that is used to add an addon to the left of an input."""

    tag = "InputLeftAddon"


class InputRightAddon(ChakraComponent):
    """The InputRightAddon component is a component that is used to add an addon to the right of an input."""

    tag = "InputRightAddon"


class InputLeftElement(ChakraComponent):
    """The InputLeftElement component is a component that is used to add an element to the left of an input."""

    tag = "InputLeftElement"


class InputRightElement(ChakraComponent):
    """The InputRightElement component is a component that is used to add an element to the right of an input."""

    tag = "InputRightElement"
