"""Component for displaying am altair graph."""
from typing import Any

from reflex.utils.serializers import serializer
from reflex.components.layout.box import Box
from reflex.components.tags import Tag
from reflex.vars import Var

try:
   import matplotlib.pyplot as plt, mpld3
   from matplotlib.figure import Figure
except ImportError:
    figure = Any
    
class Pyplot(Box):
    """Display an altair chart."""

    # The figure to display.
    fig: Var[Figure]

    # The HTML to render.
    dangerouslySetInnerHTML: Any

    def _render(self) -> Tag:
        self.dangerouslySetInnerHTML = {"__html": self.fig} 
        self.fig = None
        return super()._render()


try:
    @serializer
    def serialize_matplotlib_figure(fig: Figure) -> list:
        return mpld3.fig_to_html(fig)

except ImportError:
    pass
