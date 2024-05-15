"""A spacer component."""

from __future__ import annotations

from reflex.style import Style

from .flex import Flex


class Spacer(Flex):
    """A spacer component."""

    def add_style(self) -> Style | None:
        """Add style to the component.

        Returns:
            The style of the component.
        """
        return Style(
            {
                "flex": 1,
                "justify_self": "stretch",
                "align_self": "stretch",
            }
        )
