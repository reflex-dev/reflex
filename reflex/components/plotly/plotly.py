"""Component for displaying a plotly graph."""
from __future__ import annotations

from typing import Any, Dict, List

from reflex.base import Base
from reflex.components.component import Component, NoSSRComponent
from reflex.components.core.cond import color_mode_cond
from reflex.event import EventHandler
from reflex.utils import console
from reflex.vars import Var

try:
    from plotly.graph_objects import Figure, layout

    Template = layout.Template
except ImportError:
    console.warn("Plotly is not installed. Please run `pip install plotly`.")
    Figure = Any  # type: ignore
    Template = Any  # type: ignore


def _event_data_signature(e0: Var) -> List[Any]:
    """For plotly events with event data and no points.

    Args:
        e0: The event data.

    Returns:
        The event key extracted from the event data (if defined).
    """
    return [Var.create_safe(f"{e0}?.event", _var_is_string=False)]


def _event_points_data_signature(e0: Var) -> List[Any]:
    """For plotly events with event data containing a point array.

    Args:
        e0: The event data.

    Returns:
        The event data and the extracted points.
    """
    return [
        Var.create_safe(f"{e0}?.event", _var_is_string=False),
        Var.create_safe(
            f"extractPoints({e0}?.points)",
            _var_is_string=False,
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


class Plotly(NoSSRComponent):
    """Display a plotly graph."""

    library = "react-plotly.js@2.6.0"

    lib_dependencies: List[str] = ["plotly.js@2.22.0"]

    tag = "Plot"

    is_default = True

    # The figure to display. This can be a plotly figure or a plotly data json.
    data: Var[Figure]

    # The layout of the graph.
    layout: Var[Dict]

    # The template for visual appearance of the graph.
    template: Var[Template]

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

    def add_imports(self) -> dict[str, str]:
        """Add imports for the plotly component.

        Returns:
            The imports for the plotly component.
        """
        return {
            # For merging plotly data/layout/templates.
            "mergician@v2.0.2": "mergician"
        }

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

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the Plotly component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The Plotly component.
        """
        from plotly.io import templates

        responsive_template = color_mode_cond(
            light=Var.create_safe(templates["plotly"]).to(dict),
            dark=Var.create_safe(templates["plotly_dark"]).to(dict),
        )
        if isinstance(responsive_template, Var):
            # Mark the conditional Var as a Template to avoid type mismatch
            responsive_template = responsive_template.to(Template)
        props.setdefault("template", responsive_template)
        return super().create(*children, **props)

    def _exclude_props(self) -> set[str]:
        # These props are handled specially in the _render function
        return {"data", "layout", "template"}

    def _render(self):
        tag = super()._render()
        figure = self.data.to(dict)
        merge_dicts = []  # Data will be merged and spread from these dict Vars
        if self.layout is not None:
            # Why is this not a literal dict? Great question... it didn't work
            # reliably because of how _var_name_unwrapped strips the outer curly
            # brackets if any of the contained Vars depend on state.
            layout_dict = Var.create_safe(
                f"{{'layout': {self.layout.to(dict)._var_name_unwrapped}}}"
            ).to(dict)
            merge_dicts.append(layout_dict)
        if self.template is not None:
            template_dict = Var.create_safe(
                {"layout": {"template": self.template.to(dict)}}
            )
            template_dict._var_data = None  # To avoid stripping outer curly brackets
            merge_dicts.append(template_dict)
        if merge_dicts:
            tag.special_props.add(
                # Merge all dictionaries and spread the result over props.
                Var.create_safe(
                    f"{{...mergician({figure._var_name_unwrapped},"
                    f"{','.join(md._var_name_unwrapped for md in merge_dicts)})}}",
                    _var_is_string=False,
                ),
            )
        else:
            # Spread the figure dict over props, nothing to merge.
            tag.special_props.add(
                Var.create_safe(
                    f"{{...{figure._var_name_unwrapped}}}", _var_is_string=False
                )
            )
        return tag
