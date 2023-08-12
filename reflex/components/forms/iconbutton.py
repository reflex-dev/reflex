from reflex.components import Component
from reflex.components.media.icon import Icon
from reflex.vars import Var

class ChakraIconButtonComponent(Component):
    """A component that wraps a Chakra icon button component."""
    
    library = "@chakra-ui/react"
    

class IconButton(ChakraIconButtonComponent):
    """An icon button component."""
   
    tag = "IconButton"

    # The type of button.
    type: Var[str]

    #  A label that describes the button
    aria_label: Var[str]

    # aria-label: Var[str]

    # The icon to be used in the button.
    icon: Var[str]

    # If true, the button will be styled in its active state.
    is_active: Var[bool]

    # If true, the button will be disabled.
    is_disabled: Var[bool]

    # If true, the button will show a spinner.
    is_loading: Var[bool]

    # If true, the button will be perfectly round. Else, it'll be slightly round
    is_round: Var[bool]

    # Replace the spinner component when isLoading is set to true
    spinner: Var[str]

    @classmethod
    def create(cls, **props):
        """Initialize the IconButton component."""
        # Ensure the required props are provided
        if "icon" not in props or "aria_label" not in props:
            raise ValueError("Both 'icon' and 'aria_label' are required props for IconButton")

        # Get the Chakra UI's icon component instance
        icon_instance = Icon.create(tag=props.pop("icon"))

        return super().create(icon_instance, **props)
