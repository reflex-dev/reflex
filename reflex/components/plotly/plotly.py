"""Component for displaying a plotly graph."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple, Union

from typing_extensions import TypedDict, TypeVar

from reflex.components.component import Component, NoSSRComponent
from reflex.components.core.cond import color_mode_cond
from reflex.event import EventHandler, no_args_event_spec
from reflex.utils import console
from reflex.vars.base import LiteralVar, Var

try:
    from plotly.graph_objects import Figure, layout

    Template = layout.Template
except ImportError:
    console.warn("Plotly is not installed. Please run `pip install plotly`.")
    Figure = Any  # type: ignore
    Template = Any  # type: ignore


def _event_points_data_signature(e0: Var) -> Tuple[Var[List[Point]]]:
    """For plotly events with event data containing a point array.

    Args:
        e0: The event data.

    Returns:
        The event data and the extracted points.
    """
    return (Var(_js_expr=f"extractPoints({e0}?.points)"),)


T = TypeVar("T")

ItemOrList = Union[T, List[T]]


class BBox(TypedDict):
    """Bounding box for a point in a plotly graph."""

    x0: Union[float, int, None]
    x1: Union[float, int, None]
    y0: Union[float, int, None]
    y1: Union[float, int, None]
    z0: Union[float, int, None]
    z1: Union[float, int, None]


class Point(TypedDict):
    """A point in a plotly graph."""

    x: Union[float, int, None]
    y: Union[float, int, None]
    z: Union[float, int, None]
    lat: Union[float, int, None]
    lon: Union[float, int, None]
    curveNumber: Union[int, None]
    pointNumber: Union[int, None]
    pointNumbers: Union[List[int], None]
    pointIndex: Union[int, None]
    markerColor: Union[
        ItemOrList[
            ItemOrList[
                Union[
                    float,
                    int,
                    str,
                    None,
                ]
            ]
        ],
        None,
    ]
    markerSize: Union[
        ItemOrList[
            ItemOrList[
                Union[
                    float,
                    int,
                    None,
                ]
            ]
        ],
        None,
    ]
    bbox: Union[BBox, None]


class Plotly(NoSSRComponent):
    """Display a plotly graph."""

    library = "react-plotly.js@2.6.0"

    lib_dependencies: List[str] = ["plotly.js@2.35.2"]

    tag = "Plot"

    is_default = True

    # The figure to display. This can be a plotly figure or a plotly data json.
    data: Var[Figure]  # type: ignore

    # The layout of the graph.
    layout: Var[Dict]

    # The template for visual appearance of the graph.
    template: Var[Template]  # type: ignore

    # The config of the graph.
    config: Var[Dict]

    # If true, the graph will resize when the window is resized.
    use_resize_handler: Var[bool] = LiteralVar.create(True)

    # Fired after the plot is redrawn.
    on_after_plot: EventHandler[no_args_event_spec]

    # Fired after the plot was animated.
    on_animated: EventHandler[no_args_event_spec]

    # Fired while animating a single frame (does not currently pass data through).
    on_animating_frame: EventHandler[no_args_event_spec]

    # Fired when an animation is interrupted (to start a new animation for example).
    on_animation_interrupted: EventHandler[no_args_event_spec]

    # Fired when the plot is responsively sized.
    on_autosize: EventHandler[no_args_event_spec]

    # Fired whenever mouse moves over a plot.
    on_before_hover: EventHandler[no_args_event_spec]

    # Fired when a plotly UI button is clicked.
    on_button_clicked: EventHandler[no_args_event_spec]

    # Fired when the plot is clicked.
    on_click: EventHandler[_event_points_data_signature]

    # Fired when a selection is cleared (via double click).
    on_deselect: EventHandler[no_args_event_spec]

    # Fired when the plot is double clicked.
    on_double_click: EventHandler[no_args_event_spec]

    # Fired when a plot element is hovered over.
    on_hover: EventHandler[_event_points_data_signature]

    # Fired after the plot is layed out (zoom, pan, etc).
    on_relayout: EventHandler[no_args_event_spec]

    # Fired while the plot is being layed out.
    on_relayouting: EventHandler[no_args_event_spec]

    # Fired after the plot style is changed.
    on_restyle: EventHandler[no_args_event_spec]

    # Fired after the plot is redrawn.
    on_redraw: EventHandler[no_args_event_spec]

    # Fired after selecting plot elements.
    on_selected: EventHandler[_event_points_data_signature]

    # Fired while dragging a selection.
    on_selecting: EventHandler[_event_points_data_signature]

    # Fired while an animation is occuring.
    on_transitioning: EventHandler[no_args_event_spec]

    # Fired when a transition is stopped early.
    on_transition_interrupted: EventHandler[no_args_event_spec]

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
            markerColor: point['marker.color'],
            markerSize: point['marker.size'],
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
            light=LiteralVar.create(templates["plotly"]),
            dark=LiteralVar.create(templates["plotly_dark"]),
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
        figure = self.data.to(dict) if self.data is not None else Var.create({})
        merge_dicts = []  # Data will be merged and spread from these dict Vars
        if self.layout is not None:
            # Why is this not a literal dict? Great question... it didn't work
            # reliably because of how _var_name_unwrapped strips the outer curly
            # brackets if any of the contained Vars depend on state.
            layout_dict = LiteralVar.create({"layout": self.layout})
            merge_dicts.append(layout_dict)
        if self.template is not None:
            template_dict = LiteralVar.create({"layout": {"template": self.template}})
            merge_dicts.append(template_dict._without_data())
        if merge_dicts:
            tag.special_props.append(
                # Merge all dictionaries and spread the result over props.
                Var(
                    _js_expr=f"{{...mergician({str(figure)},"
                    f"{','.join(str(md) for md in merge_dicts)})}}",
                ),
            )
        else:
            # Spread the figure dict over props, nothing to merge.
            tag.special_props.append(Var(_js_expr=f"{{...{str(figure)}}}"))
        return tag
