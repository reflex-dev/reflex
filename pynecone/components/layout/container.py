"""A flexbox container."""

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Container(ChakraComponent):
    """A flexbox container that centers its children and sets a max width."""

    tag = "Container"

    # If true, container will center its children regardless of their width.
    center_content: Var[bool]
