"""A flexbox container."""
from typing import Optional

from reflex.components.chakra import ChakraComponent
from reflex.vars import Var


class Container(ChakraComponent):
    """A flexbox container that centers its children and sets a max width."""

    tag: str = "Container"

    # If true, container will center its children regardless of their width.
    center_content: Optional[Var[bool]] = None
