"""A switch component."""
from typing import Dict

from pynecone.components.component import EVENT_ARG
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.vars import Var


class Switch(ChakraComponent):
    """Toggleable switch component."""

    tag = "Switch"

    # If true, the switch will be checked. You'll need to pass onChange to update its value (since it is now controlled)
    is_checked: Var[bool]

    # If true, the switch will be disabled
    is_disabled: Var[bool]

    # If true and isDisabled is passed, the switch will remain tabbable but not interactive
    is_focusable: Var[bool]

    # If true, the switch is marked as invalid. Changes style of unchecked state.
    is_invalid: Var[bool]

    # If true, the switch will be readonly
    is_read_only: Var[bool]

    # If true, the switch will be required
    is_required: Var[bool]

    # The name of the input field in a switch (Useful for form submission).
    name: Var[str]

    # The spacing between the switch and its label text (0.5rem)
    spacing: Var[str]

    # The placeholder text.
    placeholder: Var[str]
    
    # The color scheme to use for the switch.
    color_scheme: Var[str]

    @classmethod
    def get_controlled_triggers(cls) -> Dict[str, Var]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            "on_change": EVENT_ARG.target.checked,
        }
        
    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a Switch component.

        Args:
            *children: The children of the component.
            **props: The props to pass to the component.

        Returns:
            The Switch component.

        Raises:
            ValueError: If children are not provided or more than one child is provided.
        """
        # If children are not provided, throw an error.
        if len(children) != 1:
            raise ValueError("Must provide children to the Switch component.")
        
        # Add the color scheme prop to the props dictionary
        if 'color_scheme' in cls._var_registry:
            props['colorScheme'] = cls._var_registry['color_scheme'].get_prop_value()
        
        # Add the children to the props dictionary
        props["children"] = children[0]

        # Create the component.
        return super().create(**props)
