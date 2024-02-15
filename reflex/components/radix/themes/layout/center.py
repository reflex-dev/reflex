"""A center component."""

from __future__ import annotations

from reflex.components.component import Component

from .flex import Flex


class Center(Flex):
    """A center component."""

    def _apply_theme(self, theme: Component):
        self.style.update(
            {
                "display": "flex",
                "align_items": "center",
                "justify_content": "center",
            }
        )
