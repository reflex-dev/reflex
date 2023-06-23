"""Component for displaying a plotly graph."""

from typing import Dict

from plotly.graph_objects import Figure

from reflex.components.component import Component
from reflex.components.tags import Tag
from reflex.vars import Var


class PlotlyLib(Component):
    """A component that wraps a plotly lib."""

    library = "react-plotly.js"


class Plotly(PlotlyLib):
    """Display a plotly graph."""

    tag = "Plot"

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

    def _get_imports(self):
        return {}

    def _get_custom_code(self) -> str:
        return """import dynamic from 'next/dynamic'
const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });
"""

    def _render(self) -> Tag:
        if (
            isinstance(self.data, Figure)
            and self.layout is None
            and self.width is not None
        ):
            layout = Var.create({"width": self.width, "height": self.height})
            assert layout is not None
            self.layout = layout

        return super()._render()
