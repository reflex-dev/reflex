"""Stack components."""

from __future__ import annotations

from reflex.components.component import Component
from reflex.components.core.breakpoints import Responsive
from reflex.components.radix.themes.base import LiteralAlign, LiteralSpacing
from reflex.vars.base import Var

from .flex import Flex, LiteralFlexDirection


class Stack(Flex):
    """A stack component."""

    # The spacing between each stack item.
    spacing: Var[Responsive[LiteralSpacing]] = Var.create("3")

    # The alignment of the stack items.
    align: Var[Responsive[LiteralAlign]] = Var.create("start")

    @classmethod
    def create(
        cls,
        *children,
        **props,
    ) -> Component:
        """Create a new instance of the component.

        Args:
            *children: The children of the stack.
            **props: The properties of the stack.

        Returns:
            The stack component.
        """
        # Apply the default classname
        given_class_name = props.pop("class_name", [])
        if not isinstance(given_class_name, list):
            given_class_name = [given_class_name]
        props["class_name"] = ["rx-Stack", *given_class_name]

        return super().create(
            *children,
            **props,
        )


class VStack(Stack):
    """A vertical stack component."""

    # The direction of the stack.
    direction: Var[Responsive[LiteralFlexDirection]] = Var.create("column")


class HStack(Stack):
    """A horizontal stack component."""

    # The direction of the stack.
    direction: Var[Responsive[LiteralFlexDirection]] = Var.create("row")


stack = Stack.create
hstack = HStack.create
vstack = VStack.create
