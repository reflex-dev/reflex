"""Component for displaying a Matplotlib graph."""

from typing import Any

from reflex.components.layout.html import HtmlDangerous
from reflex.utils.serializers import serializer

try:
    import matplotlib
    from matplotlib.figure import Figure

    matplotlib.use("Agg")
except ImportError:
    Figure = Any


class Pyplot(HtmlDangerous):
    """Display a Matplotlib chart.

    This component takes a Matplotlib figure as input and renders it within a Box layout component.
    """

    @classmethod
    def create(cls, fig: Figure, **props):
        """Create a Pyplot component.

        Args:
            fig: The Matplotlib figure to display.
            **props: The props to pass to the component.

        Returns:
            The Pyplot component.
        """
        # Create the component.
        return super().create(html=fig, **props)


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
