"""A flex item that takes up the space between its siblings."""

from __future__ import annotations

from typing import Any

from reflex_components_ui.layout.flex import Flex


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
