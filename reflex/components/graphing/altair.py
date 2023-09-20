"""Component for displaying an Altair graph."""

from typing import Any

from reflex.components.layout.box import Box
from reflex.components.tags import Tag
from reflex.utils.serializers import serializer
from reflex.vars import Var

try:
    from altair import Chart
except ImportError:
    Chart = Any


class Altair(Box):
    """Display an Altair chart.

    This component takes an Altair chart as input and renders it within a Box layout component.
    """

    # The figure to display.
    fig: Var[Chart]

    def _render(self) -> Tag:
        """Render the Bokeh figure as HTML and set it as the inner HTML of the Box component.

        Returns:
            The rendered component.
        """
        return super()._render().add_props(
                dangerouslySetInnerHTML=Var.create({"__html": self.fig})
            ).remove_props("fig")


try:
    from altair import Chart

    @serializer
    def serialize_altair_chart(chart: Chart) -> str:
        """Serialize the Altair chart to HTML.

        Args:
            chart (Chart): The Altair chart to serialize.

        Returns:
            str: The serialized Altair chart as HTML.
        """
        return chart.to_html()

except ImportError:
    pass
