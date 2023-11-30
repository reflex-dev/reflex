"""An input component."""

from typing import Any, Dict

from reflex.components.component import Component
from reflex.components.forms.debounce import DebounceInput
from reflex.components.libs.chakra import (
    ChakraComponent,
    LiteralButtonSize,
    LiteralInputVariant,
)
from reflex.constants import EventTriggers, MemoizationMode
from reflex.utils import imports
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
    variant: Var[LiteralInputVariant]

    # "lg" | "md" | "sm" | "xs"
    size: Var[LiteralButtonSize]

    # The name of the form field
    name: Var[str]

    def _get_imports(self) -> imports.ImportDict:
        return imports.merge_imports(
            super()._get_imports(),
            {"/utils/state": {imports.ImportVar(tag="set_val")}},
        )

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

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an Input component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The component.
        """
        if (
            isinstance(props.get("value"), Var) and props.get("on_change")
        ) or "debounce_timeout" in props:
            # Currently default to 50ms, which appears to be a good balance
            debounce_timeout = props.pop("debounce_timeout", 50)
            # create a debounced input if the user requests full control to avoid typing jank
            return DebounceInput.create(
                super().create(*children, **props), debounce_timeout=debounce_timeout
            )
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
