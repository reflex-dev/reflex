"""List components."""

from pynecone.components.component import Component
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class List(ChakraComponent):
    """List component is used to display list items. It renders a ul element by default."""

    tag = "List"

    # The space between each list item
    spacing: Var[str]

    # Shorthand prop for listStylePosition
    style_position: Var[str]

    # Shorthand prop for listStyleType
    style_type: Var[str]


class ListItem(ChakraComponent):
    """ListItem composes Box so you can pass all style and pseudo style props."""

    tag = "ListItem"


class OrderedList(ChakraComponent):
    """An ordered list component."""

    tag = "OrderedList"


class UnorderedList(ChakraComponent):
    """An unordered list component."""

    tag = "UnorderedList"
