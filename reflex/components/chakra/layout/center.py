"""A box that centers its contents."""

from reflex.components.libs.chakra import ChakraComponent


class Center(ChakraComponent):
    """A box that centers its contents."""

    tag = "Center"


class Square(ChakraComponent):
    """A centered square container."""

    tag = "Square"


class Circle(ChakraComponent):
    """A square container with round border-radius."""

    tag = "Circle"
