"""Component for displaying a plotly graph."""

from typing import Any, Dict, List

from reflex.components.component import NoSSRComponent
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

    # The config of the graph.
    config: Var[Dict]

    # If true, the graph will resize when the window is resized.
    use_resize_handler: Var[bool]

    def _render(self):
        tag = super()._render()
        figure = self.data.to(dict)
        if self.layout is None:
            tag.remove_props("data", "layout")
            tag.special_props.add(
                Var.create_safe(f"{{...{figure._var_name_unwrapped}}}")
            )
        else:
            tag.add_props(data=figure["data"])
        return tag