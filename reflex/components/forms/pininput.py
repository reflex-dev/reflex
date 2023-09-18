"""A pin input component."""
from __future__ import annotations

from typing import Any, Optional, Union

from reflex.components.component import Component
from reflex.components.layout import Foreach
from reflex.components.libs.chakra import ChakraComponent
from reflex.constants import EventTriggers
from reflex.utils import format
from reflex.vars import Var


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

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_CHANGE: lambda e0: [e0],
            EventTriggers.ON_COMPLETE: lambda e0: [e0],
        }

    def get_ref(self):
        """Return a reference because we actually attached the ref to the PinInputFields.

        Returns:
            None.
        """
        return None

    def _get_ref_hook(self) -> Optional[str]:
        """Override the base _get_ref_hook to handle array refs.

        Returns:
            The overrided hooks.
        """
        if self.id:
            ref = format.format_array_ref(self.id, None)
            if ref:
                return f"const {ref} = Array.from({{length:{self.length}}}, () => useRef(null));"
            return super()._get_ref_hook()

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
        if not children and "length" in props:
            _id = props.get("id", None)
            length = props["length"]
            if _id:
                children = [
                    Foreach.create(
                        list(range(length)),  # type: ignore
                        lambda ref, i: PinInputField.create(
                            key=i,
                            id=_id,
                            index=i,
                        ),
                    )
                ]
            else:
                children = [PinInputField()] * length
        return super().create(*children, **props)


class PinInputField(ChakraComponent):
    """The text field that user types in - must be a direct child of PinInput."""

    tag = "PinInputField"

    # the position of the PinInputField inside the PinInput.
    # Default to None because it is assigned by PinInput when created.
    index: Optional[Var[int]] = None

    def _get_ref_hook(self) -> Optional[str]:
        return None

    def get_ref(self):
        """Get the array ref for the pin input.

        Returns:
            The array ref.
        """
        if self.id:
            return format.format_array_ref(self.id, self.index)
