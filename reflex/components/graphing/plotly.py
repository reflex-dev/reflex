"""Component for displaying a plotly graph."""

import json
from typing import Any, Dict, List

from reflex.components.component import NoSSRComponent
from reflex.utils.serializers import serializer
from reflex.vars import Var

try:
    from plotly.graph_objects import Figure
except ImportError:
    Figure = Any  # type: ignore


class PlotlyLib(NoSSRComponent):
    """A component that wraps a plotly lib."""

    library = "react-plotly.js@2.6.0"

    lib_dependencies: List[str] = ["plotly.js@2.22.0"]


class Plotly(PlotlyLib):
    """Display a plotly graph."""

    tag = "Plot"

    is_default = True

    # The figure to display. This can be a plotly figure or a plotly data json.
    data: Var[Figure]

    # The layout of the graph.
    layout: Var[Dict]

    # The width of the graph.
    width: Var[str]

    # The height of the graph.
    height: Var[str]

    # If true, the graph will resize when the window is resized.
    use_resize_handler: Var[bool]


try:
    from plotly.graph_objects import Figure
    from plotly.io import to_json

    @serializer
    def serialize_figure(figure: Figure) -> list:
        """Serialize a plotly figure.

        Args:
            figure: The figure to serialize.

        Returns:
            The serialized figure.
        """
        return json.loads(str(to_json(figure)))["data"]

except ImportError:
    pass
