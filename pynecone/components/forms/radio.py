"""A radio component."""


from typing import Any, Set

from pynecone.components.component import Component
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.components.typography.text import Text
from pynecone.var import Var


class RadioGroup(ChakraComponent):
    """A grouping of individual radio options."""

    tag = "RadioGroup"

    # State var to bind the the input.
    value: Var[Any]

    @classmethod
    def get_controlled_triggers(cls) -> Set[str]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            The controlled event triggers.
        """
        return {"on_change"}

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a radio group component.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The component.
        """
        if len(children) == 1 and isinstance(children[0], list):
            children = [Radio.create(child) for child in children[0]]
        return super().create(*children, **props)


class Radio(Text):
    """Radios are used when only one choice may be selected in a series of options."""

    tag = "Radio"

    # Value of radio.
    value: Var[Any]

    # The default value.
    default_value: Var[Any]

    # The color scheme.
    color_scheme: Var[str]

    # If true, the radio will be initially checked.
    default_checked: Var[bool]

    # If true, the radio will be checked. You'll need to pass onChange to update its value (since it is now controlled)
    is_checked: Var[bool]

    # If true, the radio will be disabled.
    is_disabled: Var[bool]

    # If true, the radio button will be invalid. This also sets `aria-invalid` to true.
    is_invalid: Var[bool]

    # If true, the radio will be read-only
    is_read_only: Var[bool]

    # If true, the radio button will be required. This also sets `aria-required` to true.
    is_required: Var[bool]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a radio component.

        By default, the value is bound to the first child.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The radio component.
        """
        if "value" not in props:
            assert len(children) == 1
            props["value"] = children[0]
        return super().create(*children, **props)
