"""A center component."""
from __future__ import annotations

from reflex.components.component import Component
from reflex.components.el.elements.typography import Div


class Center(Div):
    """A center component."""

    def _apply_theme(self, theme: Component | None):
        self.style.update(
            {
                "display": "flex",
                "align_items": "center",
                "justify_content": "center",
            }
        )


center = Center.create
