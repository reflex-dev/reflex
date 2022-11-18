"""A box that centers its contents."""

from pynecone.components.libs.chakra import ChakraComponent


class Center(ChakraComponent):
    """Center is a layout component that centers its child within itself. It's useful for centering text, images, and other elements. All box can be used on center to style."""

    tag = "Center"


class Square(ChakraComponent):
    """Square centers its child given size (width and height). All box props can be used on Square."""

    tag = "Square"


class Circle(ChakraComponent):
    """Circle a Square with round border-radius. All box props can be used on Circle."""

    tag = "Circle"
