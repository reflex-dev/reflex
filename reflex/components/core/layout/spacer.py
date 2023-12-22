"""A spacer component."""
from __future__ import annotations

from reflex.components.component import Component
from reflex.components.el.elements.typography import Div


class Spacer(Div):
    """A spacer component."""

    def _apply_theme(self, theme: Component | None):
        self.style.update(
            {
                "flex": 1,
                "justify_self": "stretch",
                "align_self": "stretch",
            }
        )


spacer = Spacer.create
