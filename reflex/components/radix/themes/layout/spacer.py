"""A spacer component."""

from __future__ import annotations

from typing import Any

from .flex import Flex


class Spacer(Flex):
    """A spacer component."""

    def add_style(self) -> dict[str, Any] | None:
        """Add style to the component.

        Returns:
            The style of the component.
        """
        return {
            "flex": 1,
            "justify_self": "stretch",
            "align_self": "stretch",
        }


spacer = Spacer.create
