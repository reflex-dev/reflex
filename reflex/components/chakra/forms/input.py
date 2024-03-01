"""An input component."""
from typing import Any, Dict, Optional

from reflex.components.chakra import (
    ChakraComponent,
    LiteralButtonSize,
    LiteralInputVariant,
)
from reflex.components.component import Component
from reflex.components.core.debounce import DebounceInput
from reflex.components.literals import LiteralInputType
from reflex.constants import EventTriggers, MemoizationMode
from reflex.utils import imports
from reflex.vars import Var


class Input(ChakraComponent):
    """The Input component is a component that is used to get user input in a text field."""

    tag: str = "Input"

    # State var to bind the input.
    value: Optional[Var[str]] = None

    # The default value of the input.
    default_value: Optional[Var[str]] = None

    # The placeholder text.
    placeholder: Optional[Var[str]] = None

    # The type of input.
    type_: Optional[Var[LiteralInputType]] = None

    # The border color when the input is invalid.
    error_border_color: Optional[Var[str]] = None

    # The border color when the input is focused.
    focus_border_color: Optional[Var[str]] = None

    # If true, the form control will be disabled. This has 2 side effects - The FormLabel will have `data-disabled` attribute - The form element (e.g, Input) will be disabled
    is_disabled: Optional[Var[bool]] = None

    # If true, the form control will be invalid. This has 2 side effects - The FormLabel and FormErrorIcon will have `data-invalid` set to true - The form element (e.g, Input) will have `aria-invalid` set to true
    is_invalid: Optional[Var[bool]] = None

    # If true, the form control will be readonly.
    is_read_only: Optional[Var[bool]] = None

    # If true, the form control will be required. This has 2 side effects - The FormLabel will show a required indicator - The form element (e.g, Input) will have `aria-required` set to true
    is_required: Optional[Var[bool]] = None

    # "outline" | "filled" | "flushed" | "unstyled"
    variant: Optional[Var[LiteralInputVariant]] = None

    # "lg" | "md" | "sm" | "xs"
    size: Optional[Var[LiteralButtonSize]] = None

    # The name of the form field
    name: Optional[Var[str]] = None

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
        if props.get("value") is not None and props.get("on_change"):
            # create a debounced input if the user requests full control to avoid typing jank
            return DebounceInput.create(super().create(*children, **props))
        return super().create(*children, **props)


class InputGroup(ChakraComponent):
    """The InputGroup component is a component that is used to group a set of inputs."""

    tag: str = "InputGroup"

    _memoization_mode = MemoizationMode(recursive=False)


class InputLeftAddon(ChakraComponent):
    """The InputLeftAddon component is a component that is used to add an addon to the left of an input."""

    tag: str = "InputLeftAddon"


class InputRightAddon(ChakraComponent):
    """The InputRightAddon component is a component that is used to add an addon to the right of an input."""

    tag: str = "InputRightAddon"


class InputLeftElement(ChakraComponent):
    """The InputLeftElement component is a component that is used to add an element to the left of an input."""

    tag: str = "InputLeftElement"


class InputRightElement(ChakraComponent):
    """The InputRightElement component is a component that is used to add an element to the right of an input."""

    tag: str = "InputRightElement"
