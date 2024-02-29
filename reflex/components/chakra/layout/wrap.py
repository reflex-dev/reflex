"""Container to stack elements with spacing."""
from typing import Optional

from reflex.components.chakra import ChakraComponent
from reflex.components.component import Component
from reflex.vars import Var


class Wrap(ChakraComponent):
    """Layout component used to add space between elements and wrap automatically if there isn't enough space."""

    tag = "Wrap"

    # How to align the items.
    align: Optional[Var[str]] = None

    # The flex direction of the wrap.
    direction: Optional[Var[str]] = None

    # How to justify the items.
    justify: Optional[Var[str]] = None

    # Whether to wrap children in `rx.wrap_item`.
    should_wrap_children: Optional[Var[bool]] = None

    # The spacing between the items.
    spacing: Optional[Var[str]] = None

    # The horizontal spacing between the items.
    spacing_x: Optional[Var[str]] = None

    # The vertical spacing between the items.
    spacing_y: Optional[Var[str]] = None

    @classmethod
    def create(cls, *children, items=None, **props) -> Component:
        """Return a wrap component.

        Args:
            *children: The children of the component.
            items (list): The items of the wrap component.
            **props: The properties of the component.

        Returns:
            The wrap component.
        """
        if len(children) == 0:
            children = []
            for item in items or []:
                children.append(WrapItem.create(*item))

        return super().create(*children, **props)


class WrapItem(ChakraComponent):
    """Item of the Wrap component."""

    tag = "WrapItem"
