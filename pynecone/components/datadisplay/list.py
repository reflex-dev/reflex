"""List components."""

from pynecone.components.component import Component
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class List(ChakraComponent):
    """Display a list of items."""

    tag = "List"

    # The space between each list item
    spacing: Var[str]

    # Shorthand prop for listStylePosition
    style_position: Var[str]

    # Shorthand prop for listStyleType
    style_type: Var[str]


class ListItem(ChakraComponent):
    """A single list item."""

    tag = "ListItem"


class OrderedList(ChakraComponent):
    """An ordered list component with numbers."""

    tag = "OrderedList"


class UnorderedList(ChakraComponent):
    """An unordered list component with bullets."""

    tag = "UnorderedList"
