"""An image component."""

from pynecone.components.component import Component


class ChakraIconComponent(Component):
    """A component that wraps a chakra icon component."""

    library = "@chakra-ui/icons"


class Icon(ChakraIconComponent):
    """The Avatar component is used to represent a user, and displays the profile picture, initials or fallback icon."""

    tag = "None"
