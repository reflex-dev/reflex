"""React fragments to enable bare returns of component trees from functions."""
from nextpy.components.component import Component


class Fragment(Component):
    """A React fragment to return multiple components from a function without wrapping it in a container."""

    library = "react"
    tag = "Fragment"
