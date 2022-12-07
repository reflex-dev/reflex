"""An image component."""

from pynecone.components.component import Component


class ChakraIconComponent(Component):
    """A component that wraps a Chakra icon component."""

    library = "@chakra-ui/icons"


class Icon(ChakraIconComponent):
    """An image icon."""

    tag = "None"
