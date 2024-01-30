"""Stack components."""
from __future__ import annotations

from typing import Literal, Optional

from reflex.components.component import Component

from .flex import Flex

LiteralJustify = Literal["start", "center", "end"]
LiteralAlign = Literal["start", "center", "end", "stretch"]


class Stack(Flex):
    """A stack component."""

    @classmethod
    def create(
        cls,
        *children,
        justify: Optional[LiteralJustify] = "start",
        align: Optional[LiteralAlign] = "center",
        spacing: Optional[str] = "0.5rem",
        **props,
    ) -> Component:
        """Create a new instance of the component.

        Args:
            *children: The children of the stack.
            justify: The justify of the stack elements.
            align: The alignment of the stack elements.
            spacing: The spacing between each stack item.
            **props: The properties of the stack.

        Returns:
            The stack component.
        """
        style = props.setdefault("style", {})
        style.update(
            {
                "alignItems": align,
                "justifyContent": justify,
                "gap": spacing,
            }
        )
        return super().create(*children, **props)


class VStack(Stack):
    """A vertical stack component."""

    def _apply_theme(self, theme: Component):
        self.style.update({"flex_direction": "column"})


class HStack(Stack):
    """A horizontal stack component."""

    def _apply_theme(self, theme: Component):
        self.style.update({"flex_direction": "row"})
