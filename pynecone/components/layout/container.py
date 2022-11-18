"""A flexbox container."""

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Container(ChakraComponent):
    """Container composes Box so you can pass all Box related props in addition to this."""

    tag = "Container"

    # If true, container will center its children regardless of their width.
    center_content: Var[bool]
