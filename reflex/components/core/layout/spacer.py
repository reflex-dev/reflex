"""A spacer component."""
from reflex.components.component import Component
from reflex.components.el.elements.typography import Div
from reflex.style import Style


class Spacer(Div):
    """A spacer component."""

    def _apply_theme(self, theme: Component | None):
        self.style = Style(
            {
                "flex": 1,
                "justify_self": "stretch",
                "align_self": "stretch",
                **self.style,
            }
        )


spacer = Spacer.create
