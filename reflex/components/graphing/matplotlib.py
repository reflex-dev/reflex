"""Component for displaying a Matplotlib graph."""

from typing import Any

from reflex.components.layout.box import Box
from reflex.components.tags import Tag
from reflex.utils.serializers import serializer
from reflex.vars import Var

try:
    import matplotlib
    from matplotlib.figure import Figure

    matplotlib.use("Agg")
except ImportError:
    Figure = Any


class Pyplot(Box):
    """Display a Matplotlib chart.

    This component takes a Matplotlib figure as input and renders it within a Box layout component.
    """

    # The figure to display.
    fig: Var[Figure]

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
    import mpld3
    from matplotlib.figure import Figure

    @serializer
    def serialize_matplotlib_figure(fig: Figure) -> str:
        """Serialize the Matplotlib figure to HTML.

        Args:
            fig (Figure): The Matplotlib figure to serialize.

        Returns:
            str: The serialized Matplotlib figure as HTML.
        """
        return mpld3.fig_to_html(fig)

except ImportError:
    pass
