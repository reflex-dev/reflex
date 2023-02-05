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

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a list component.

        Args:
            children: The children of the component.
            props: The properties of the component.

        Returns:
            The list component.
        """
        if not children:
            children = []
            items = props.pop("items")
            for item in items:
                children.append(ListItem.create(*item))
        return super().create(*children, **props)


class ListItem(ChakraComponent):
    """A single list item."""

    tag = "ListItem"


class OrderedList(List):
    """An ordered list component with numbers."""

    tag = "OrderedList"


class UnorderedList(List):
    """An unordered list component with bullets."""

    tag = "UnorderedList"
