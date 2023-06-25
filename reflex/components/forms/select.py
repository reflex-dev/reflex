"""A select component."""

from typing import Any, Dict, List

from reflex.components.component import EVENT_ARG, Component
from reflex.components.layout.foreach import Foreach
from reflex.components.libs.chakra import ChakraComponent
from reflex.components.typography.text import Text
from reflex.utils import types
from reflex.vars import Var


class Select(ChakraComponent):
    """Select component is a component that allows users pick a value from predefined options. Ideally, it should be used when there are more than 5 options, otherwise you might consider using a radio group instead."""

    tag = "Select"

    # State var to bind the select.
    value: Var[str]

    # The default value of the select.
    default_value: Var[str]

    # The placeholder text.
    placeholder: Var[str]

    # The border color when the select is invalid.
    error_border_color: Var[str]

    # The border color when the select is focused.
    focus_border_color: Var[str]

    # If true, the select will be disabled.
    is_disabled: Var[bool]

    # If true, the form control will be invalid. This has 2 side effects: - The FormLabel and FormErrorIcon will have `data-invalid` set to true - The form element (e.g, Input) will have `aria-invalid` set to true
    is_invalid: Var[bool]

    # If true, the form control will be readonly
    is_read_only: Var[bool]

    # If true, the form control will be required. This has 2 side effects: - The FormLabel will show a required indicator - The form element (e.g, Input) will have `aria-required` set to true
    is_required: Var[bool]

    # "outline" | "filled" | "flushed" | "unstyled"
    variant: Var[str]

    # The size of the select.
    size: Var[str]

    @classmethod
    def get_controlled_triggers(cls) -> Dict[str, Var]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            "on_change": EVENT_ARG.target.value,
        }

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a select component.

        If a list is provided as the first children, a default component
        will be created for each item in the list.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The component.
        """
        if len(children) == 1 and isinstance(children[0], list):
            children = [Option.create(child) for child in children[0]]
        if (
            len(children) == 1
            and isinstance(children[0], Var)
            and types._issubclass(children[0].type_, List)
        ):
            children = [Foreach.create(children[0], lambda item: Option.create(item))]
        return super().create(*children, **props)


class Option(Text):
    """A select option."""

    tag = "option"

    value: Var[Any]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a select option component.

        By default, the value of the option is the text of the option.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The component.
        """
        if "value" not in props:
            assert len(children) == 1
            props["value"] = children[0]
        return super().create(*children, **props)
