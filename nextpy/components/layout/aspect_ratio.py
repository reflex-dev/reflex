"""A AspectRatio component."""

from nextpy.components.libs.chakra import ChakraComponent
from nextpy.core.vars import Var


class AspectRatio(ChakraComponent):
    """AspectRatio component is used to embed responsive videos and maps, etc."""

    tag = "AspectRatio"

    # The aspect ratio of the Box
    ratio: Var[float]
