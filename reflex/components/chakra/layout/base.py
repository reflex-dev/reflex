"""The base class for all Chakra layout components."""

from reflex.components.chakra import ChakraComponent


class ChakraLayoutComponent(ChakraComponent):
    """A component that wraps a Chakra component."""

    library = "@chakra-ui/layout@2.3.1"
