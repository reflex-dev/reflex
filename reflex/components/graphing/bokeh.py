"""Component for displaying a Bokeh graph."""

from typing import Any

from reflex.components.layout.html import HtmlDangerous

from reflex.components.tags import Tag
from reflex.utils.serializers import serializer
from reflex.vars import Var

try:
    from bokeh.plotting import figure
except ImportError:
    figure = Any


class Bokeh(HtmlDangerous):
    """Display a Bokeh chart.
    This component takes a Bokeh figure as input and renders it within a Box layout component.
    """

    @classmethod
    def create(cls, fig: figure, **props):  # type: ignore
        """Create a Bokeh component.

        Args:
            fig: The Bokeh figure to display.
            **props: The props to pass to the component.

        Returns:
            The Bokeh component.
        """
        # Create the component.
        return super().create(html=fig, **props)


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
        return f"`{file_html(fig)}`"

except ImportError:
    pass