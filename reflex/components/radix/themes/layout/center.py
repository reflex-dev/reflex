"""A center component."""

from __future__ import annotations

from reflex.style import Style

from .flex import Flex


class Center(Flex):
    """A center component."""

    def add_style(self) -> Style | None:
        """Add style that center the content.

        Returns:
            The style of the component.
        """
        return Style(
            {
                "display": "flex",
                "align_items": "center",
                "justify_content": "center",
            }
        )
