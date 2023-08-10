from reflex.components import Component
from reflex.components.media.icon import Icon

class ChakraIconButtonComponent(Component):
    """A component that wraps a Chakra icon button component."""
    
    library = "@chakra-ui/react"

class IconButton(ChakraIconButtonComponent):
    """An icon button component."""
    tag = "IconButton"

    @classmethod
    def create(cls, **props):
        """Initialize the IconButton component."""
        # Ensure the required props are provided
        if "icon" not in props or "aria_label" not in props:
            raise ValueError("Both 'icon' and 'aria_label' are required props for IconButton")

        # Get the Chakra UI's icon component instance
        icon_instance = Icon.create(tag=props.pop("icon"))
        print("tag:",icon_instance.tag)
        # Return the IconButton component using the tag of icon_instance instead of the instance itself
        return super().create(icon=icon_instance, aria_label=props.pop("aria_label"), **props)
