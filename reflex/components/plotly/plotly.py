"""Component for displaying a plotly graph."""
from typing import Any, Dict, List, Optional

from reflex.components.component import NoSSRComponent
from reflex.vars import Var

try:
    from plotly.graph_objects import Figure
except ImportError:
    Figure = Any  # type: ignore


class PlotlyLib(NoSSRComponent):
    """A component that wraps a plotly lib."""

    library: str = "react-plotly.js@2.6.0"

    lib_dependencies: List[str] = ["plotly.js@2.22.0"]


class Plotly(PlotlyLib):
    """Display a plotly graph."""

    tag: str = "Plot"

    is_default: bool = True

    # The figure to display. This can be a plotly figure or a plotly data json.
    data: Optional[Var[Figure]] = None

    # The layout of the graph.
    layout: Optional[Var[Dict]] = None

    # The config of the graph.
    config: Optional[Var[Dict]] = None

    # The width of the graph.
    width: Optional[Var[str]] = None

    # The height of the graph.
    height: Optional[Var[str]] = None

    # If true, the graph will resize when the window is resized.
    use_resize_handler: Optional[Var[bool]] = None
