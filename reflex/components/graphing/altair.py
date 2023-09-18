"""Component for displaying am altair graph."""
from typing import Any

from reflex.utils.serializers import serializer
from reflex.components.layout.box import Box
from reflex.components.tags import Tag
from reflex.vars import Var

try:
    from altair import Chart
except ImportError:
    Chart = Any
    
class Altair(Box):
    """Display an altair chart."""

    # The figure to display.
    fig: Var[Chart]

    # The HTML to render.
    dangerouslySetInnerHTML: Any

    def _render(self) -> Tag:
        self.dangerouslySetInnerHTML = {"__html": self.fig} 
        self.fig = None
        return super()._render()


try:
    @serializer
    def serialize_altair_chart(chart: Chart) -> list:
        return chart.to_html()

except ImportError:
    pass
