"""Component for displaying a plotly graph."""
from __future__ import annotations

from typing import Any, Dict, List

from reflex.base import Base
from reflex.components.component import NoSSRComponent
from reflex.event import EventHandler
from reflex.vars import Var

try:
    from plotly.graph_objects import Figure
except ImportError:
    Figure = Any  # type: ignore


def _event_data_signature(e0: Var) -> List[Any]:
    """For plotly events with event data and no points.

    Args:
        e0: The event data.

    Returns:
        The event key extracted from the event data (if defined).
    """
    return [Var.create_safe(f"{e0}?.event")]


def _event_points_data_signature(e0: Var) -> List[Any]:
    """For plotly events with event data containing a point array.

    Args:
        e0: The event data.

    Returns:
        The event data and the extracted points.
    """
    return [
        Var.create_safe(f"{e0}?.event"),
        Var.create_safe(
            f"extractPoints({e0}?.points)",
        ),
    ]


class _ButtonClickData(Base):
    """Event data structure for plotly UI buttons."""

    menu: Any
    button: Any
    active: Any


def _button_click_signature(e0: _ButtonClickData) -> List[Any]:
    """For plotly button click events.

    Args:
        e0: The button click data.

    Returns:
        The menu, button, and active state.
    """
    return [e0.menu, e0.button, e0.active]


def _passthrough_signature(e0: Var) -> List[Any]:
    """For plotly events with arbitrary serializable data, passed through directly.

    Args:
        e0: The event data.

    Returns:
        The event data.
    """
    return [e0]


def _null_signature() -> List[Any]:
    """For plotly events with no data or non-serializable data. Nothing passed through.

    Returns:
        An empty list (nothing passed through).
    """
    return []


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
    use_resize_handler: Var[bool] = Var.create_safe(True)

    # Fired after the plot is redrawn.
    on_after_plot: EventHandler[_passthrough_signature]

    # Fired after the plot was animated.
    on_animated: EventHandler[_null_signature]

    # Fired while animating a single frame (does not currently pass data through).
    on_animating_frame: EventHandler[_null_signature]

    # Fired when an animation is interrupted (to start a new animation for example).
    on_animation_interrupted: EventHandler[_null_signature]

    # Fired when the plot is responsively sized.
    on_autosize: EventHandler[_event_data_signature]

    # Fired whenever mouse moves over a plot.
    on_before_hover: EventHandler[_event_data_signature]

    # Fired when a plotly UI button is clicked.
    on_button_clicked: EventHandler[_button_click_signature]

    # Fired when the plot is clicked.
    on_click: EventHandler[_event_points_data_signature]

    # Fired when a selection is cleared (via double click).
    on_deselect: EventHandler[_null_signature]

    # Fired when the plot is double clicked.
    on_double_click: EventHandler[_passthrough_signature]

    # Fired when a plot element is hovered over.
    on_hover: EventHandler[_event_points_data_signature]

    # Fired after the plot is layed out (zoom, pan, etc).
    on_relayout: EventHandler[_passthrough_signature]

    # Fired while the plot is being layed out.
    on_relayouting: EventHandler[_passthrough_signature]

    # Fired after the plot style is changed.
    on_restyle: EventHandler[_passthrough_signature]

    # Fired after the plot is redrawn.
    on_redraw: EventHandler[_event_data_signature]

    # Fired after selecting plot elements.
    on_selected: EventHandler[_event_points_data_signature]

    # Fired while dragging a selection.
    on_selecting: EventHandler[_event_points_data_signature]

    # Fired while an animation is occuring.
    on_transitioning: EventHandler[_event_data_signature]

    # Fired when a transition is stopped early.
    on_transition_interrupted: EventHandler[_event_data_signature]

    # Fired when a hovered element is no longer hovered.
    on_unhover: EventHandler[_event_points_data_signature]

    def add_custom_code(self) -> list[str]:
        """Add custom codes for processing the plotly points data.

        Returns:
            Custom code snippets for the module level.
        """
        return [
            "const removeUndefined = (obj) => {Object.keys(obj).forEach(key => obj[key] === undefined && delete obj[key]); return obj}",
            """
const extractPoints = (points) => {
    if (!points) return [];
    return points.map(point => {
        const bbox = point.bbox ? removeUndefined({
            x0: point.bbox.x0,
            x1: point.bbox.x1,
            y0: point.bbox.y0,
            y1: point.bbox.y1,
            z0: point.bbox.y0,
            z1: point.bbox.y1,
        }) : undefined;
        return removeUndefined({
            x: point.x,
            y: point.y,
            z: point.z,
            lat: point.lat,
            lon: point.lon,
            curveNumber: point.curveNumber,
            pointNumber: point.pointNumber,
            pointNumbers: point.pointNumbers,
            pointIndex: point.pointIndex,
            'marker.color': point['marker.color'],
            'marker.size': point['marker.size'],
            bbox: bbox,
        })
    })
}
""",
        ]

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
