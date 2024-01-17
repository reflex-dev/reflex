"""A flexbox container."""


from reflex.components.chakra.layout import ChakraLayoutComponent
from reflex.vars import Var


class Container(ChakraLayoutComponent):
    """A flexbox container that centers its children and sets a max width."""

    tag = "Container"

    # If true, container will center its children regardless of their width.
    center_content: Var[bool]
