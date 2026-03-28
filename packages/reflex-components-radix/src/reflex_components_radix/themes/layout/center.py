"""A center component."""

from __future__ import annotations

from typing import Any

from .flex import Flex


class Center(Flex):
    """A center component."""

    def add_style(self) -> dict[str, Any] | None:
        """Add style that center the content.

        Returns:
            The style of the component.
        """
        return {
            "display": "flex",
            "align_items": "center",
            "justify_content": "center",
        }


center = Center.create
