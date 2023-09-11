"""Component for displaying a plotly graph."""

from typing import Dict, List, Any

import altair as alt

from reflex.components.layout.box import Box
from reflex.components.tags import Tag
from reflex.vars import Var


class Altair(Box):
    """Render the html.

    Returns:
        The code to render the  html component.
    """

    # The figure to display.
    fig: Var[alt.Chart]

    # The HTML to render.
    dangerouslySetInnerHTML: Any

    def _render(self) -> Tag:
        self.dangerouslySetInnerHTML = {"__html": self.fig} 

        return super()._render()
