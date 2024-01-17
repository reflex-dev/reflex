"""A AspectRatio component."""

from reflex.components.chakra.layout import ChakraLayoutComponent
from reflex.vars import Var


class AspectRatio(ChakraLayoutComponent):
    """AspectRatio component is used to embed responsive videos and maps, etc."""

    tag = "AspectRatio"

    # The aspect ratio of the Box
    ratio: Var[float]
