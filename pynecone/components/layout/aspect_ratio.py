"""A AspectRatio component."""

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.vars import Var


class AspectRatio(ChakraComponent):
    """AspectRatio component is used to embed responsive videos and maps, etc."""

    tag = "AspectRatio"

    # The aspect ratio of the Box
    ratio: Var[float]
