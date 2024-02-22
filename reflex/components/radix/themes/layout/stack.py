"""Stack components."""

from __future__ import annotations

from reflex.components.component import Component

from ..base import LiteralAlign, LiteralSpacing
from .flex import Flex


class Stack(Flex):
    """A stack component."""

    @classmethod
    def create(
        cls,
        *children,
        spacing: LiteralSpacing = "2",
        align: LiteralAlign = "start",
        **props,
    ) -> Component:
        """Create a new instance of the component.

        Args:
            *children: The children of the stack.
            spacing: The spacing between each stack item.
            align: The alignment of the stack items.
            **props: The properties of the stack.

        Returns:
            The stack component.
        """
        return super().create(
            *children,
            spacing=spacing,
            align=align,
            **props,
        )


class VStack(Stack):
    """A vertical stack component."""

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a new instance of the component.

        Args:
            *children: The children of the stack.
            **props: The properties of the stack.

        Returns:
            The stack component.
        """
        return super().create(*children, direction="column", **props)


class HStack(Stack):
    """A horizontal stack component."""

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a new instance of the component.

        Args:
            *children: The children of the stack.
            **props: The properties of the stack.

        Returns:
            The stack component.
        """
        return super().create(*children, direction="row", **props)
