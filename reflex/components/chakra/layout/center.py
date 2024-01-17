"""A box that centers its contents."""

from reflex.components.chakra.layout import ChakraLayoutComponent


class Center(ChakraLayoutComponent):
    """A box that centers its contents."""

    tag = "Center"


class Square(ChakraLayoutComponent):
    """A centered square container."""

    tag = "Square"


class Circle(ChakraLayoutComponent):
    """A square container with round border-radius."""

    tag = "Circle"
