"""Stack components."""

from __future__ import annotations

from reflex.components.component import Component
from reflex.vars import Var

from ..base import LiteralAlign, LiteralSpacing
from .flex import Flex, LiteralFlexDirection


class Stack(Flex):
    """A stack component."""

    @classmethod
    def create(
        cls,
        *children,
        spacing: LiteralSpacing = "3",
        align: LiteralAlign = "start",
        width: str = "100%",
        child_width: str = "100%",
        child_flex_shrink: str = "1",
        **props,
    ) -> Component:
        """Create a new instance of the component.

        Args:
            *children: The children of the stack.
            spacing: The spacing between each stack item.
            align: The alignment of the stack items.
            width: The CSS width of the stack.
            child_width: The CSS width of non-inline stack children.
            child_flex_shrink: The flex shrink value of non-inline stack children.
            **props: The properties of the stack.

        Returns:
            The stack component.
        """
        style = props.setdefault("style", {})
        child_block_style = style.setdefault(
            "> :where(div:not(.rt-Box, .rx-Upload), button:not(.rt-IconButton), input, select, textarea, table)",
            {},
        )
        child_block_style.setdefault("width", child_width)
        child_block_style.setdefault("flex_shrink", child_flex_shrink)
        return super().create(
            *children,
            spacing=spacing,
            align=align,
            width=width,
            **props,
        )


class VStack(Stack):
    """A vertical stack component."""

    # The direction of the stack.
    direction: Var[LiteralFlexDirection] = "column"  # type: ignore


class HStack(Stack):
    """A horizontal stack component."""

    # The direction of the stack.
    direction: Var[LiteralFlexDirection] = "row"  # type: ignore
