"""Component for displaying a Bokeh graph."""

from typing import Any

from reflex.components.layout.box import Box
from reflex.components.tags import Tag
from reflex.utils.serializers import serializer
from reflex.vars import Var

try:
    from bokeh.plotting import figure
except ImportError:
    figure = Any


class Bokeh(Box):
    """Display a Bokeh chart.

    This component takes a Bokeh figure as input and renders it within a Box layout component.
    """

    # The figure to display.
    fig: Var[figure]

    def _render(self) -> Tag:
        """Render the Bokeh figure as HTML and set it as the inner HTML of the Box component.

        Returns:
            The rendered component.
        """
        return (
            super()
            ._render()
            .add_props(dangerouslySetInnerHTML=Var.create({"__html": self.fig}))
            .remove_props("fig")
        )


try:
    from bokeh.embed import file_html
    from bokeh.plotting import figure

    @serializer
    def serialize_bokeh_chart(fig: figure) -> str:
        """Serialize the Bokeh figure to HTML.

        Args:
            fig (figure): The Bokeh figure to serialize.

        Returns:
            str: The serialized Bokeh figure as HTML.
        """
        return file_html(fig)

except ImportError:
    pass
