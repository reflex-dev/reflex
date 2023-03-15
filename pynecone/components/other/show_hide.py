"""A Show and Hide component."""
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class ChakraShowHideComponent(ChakraComponent):
    """Wrappers for other elements and components to show or hide them based on a media query."""

    # A custom css media query that determines when the children are rendered.
    breakpoint: Var[str]

    # A value from the breakpoints section in the theme. Will render children from that breakpoint and above
    above: Var[str]

    # A value from the breakpoints section in the theme. Will render children from that breakpoint and below
    below: Var[str]


class Show(ChakraShowHideComponent):
    """Show the children if the media query matches."""

    tag = "Show"


class Hide(ChakraShowHideComponent):
    """Hide the children if the media query matches."""

    tag = "Hide"
