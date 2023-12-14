"""A box that centers its contents."""

from reflex.components.libs.chakra import ChakraComponent


class Center(ChakraComponent):
    """A box that centers its contents."""

    tag: str = "Center"


class Square(ChakraComponent):
    """A centered square container."""

    tag: str = "Square"


class Circle(ChakraComponent):
    """A square container with round border-radius."""

    tag: str = "Circle"
