"""A center component."""
from __future__ import annotations

from reflex.components.component import Component
from reflex.components.el.elements.typography import Div
from reflex.style import Style


class Center(Div):
    """A center component."""

    def _apply_theme(self, theme: Component | None):
        self.style = Style(
            {
                "display": "flex",
                "align_items": "center",
                "justify_content": "center",
                **self.style,
            }
        )


center = Center.create
