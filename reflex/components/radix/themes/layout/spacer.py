"""A spacer component."""

from __future__ import annotations

from reflex.components.component import Component

from .flex import Flex


class Spacer(Flex):
    """A spacer component."""

    def _apply_theme(self, theme: Component):
        self.style.update(
            {
                "flex": 1,
                "justify_self": "stretch",
                "align_self": "stretch",
            }
        )
