"""A Keyboard Key Component."""

from reflex.components.chakra import ChakraComponent


class KeyboardKey(ChakraComponent):
    """Display a keyboard key text."""

    library = "@chakra-ui/layout@2.3.1"

    tag = "Kbd"
