"""Component for displaying am altair graph."""
from typing import Any

from reflex.utils.serializers import serializer
from reflex.components.layout.box import Box
from reflex.components.tags import Tag
from reflex.vars import Var

try:
    from bokeh.plotting import figure
except ImportError:
    figure = Any
    
class Bokeh(Box):
    """Display an altair chart."""

    # The figure to display.
    fig: Var[figure]

    # The HTML to render.
    dangerouslySetInnerHTML: Any

    def _render(self) -> Tag:
        self.dangerouslySetInnerHTML = {"__html": self.fig} 
        self.fig = None
        return super()._render()


try:
    from bokeh.embed import file_html

    @serializer
    def serialize_altair_chart(fig: figure) -> list:
        return file_html(fig)

except ImportError:
    pass
