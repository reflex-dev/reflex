"""Stack components."""

from __future__ import annotations

from reflex_base.components.component import Component, field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import LiteralAlign, LiteralSpacing

from .flex import Flex, LiteralFlexDirection


class Stack(Flex):
    """A stack component."""

    spacing: Var[Responsive[LiteralSpacing]] = field(
        default=Var.create("3"), doc="The spacing between each stack item."
    )

    align: Var[Responsive[LiteralAlign]] = field(
        default=Var.create("start"), doc="The alignment of the stack items."
    )

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

    direction: Var[Responsive[LiteralFlexDirection]] = field(
        default=Var.create("column"), doc="The direction of the stack."
    )


class HStack(Stack):
    """A horizontal stack component."""

    direction: Var[Responsive[LiteralFlexDirection]] = field(
        default=Var.create("row"), doc="The direction of the stack."
    )


stack = Stack.create
hstack = HStack.create
vstack = VStack.create
