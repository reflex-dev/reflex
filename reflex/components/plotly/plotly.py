"""Component for displaying a plotly graph."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict, TypeVar

from reflex.components.component import Component, NoSSRComponent
from reflex.components.core.cond import color_mode_cond
from reflex.event import EventHandler, no_args_event_spec
from reflex.utils import console
from reflex.utils.imports import ImportDict, ImportVar
from reflex.vars.base import LiteralVar, Var

try:
    from plotly.graph_objs import Figure
    from plotly.graph_objs.layout import Template

except ImportError:
    console.warn("Plotly is not installed. Please run `pip install plotly`.")
    if not TYPE_CHECKING:
        Figure = Any
        Template = Any


def _event_points_data_signature(e0: Var) -> tuple[Var[list[Point]]]:
    """For plotly events with event data containing a point array.

    Args:
        e0: The event data.

    Returns:
        The event data and the extracted points.
    """
    return (Var(_js_expr=f"extractPoints({e0}?.points)"),)


T = TypeVar("T")

ItemOrList = T | list[T]


class BBox(TypedDict):
    """Bounding box for a point in a plotly graph."""

    x0: float | int | None
    x1: float | int | None
    y0: float | int | None
    y1: float | int | None
    z0: float | int | None
    z1: float | int | None


class Point(TypedDict):
    """A point in a plotly graph."""

    x: float | int | None
    y: float | int | None
    z: float | int | None
    lat: float | int | None
    lon: float | int | None
    curveNumber: int | None
    pointNumber: int | None
    pointNumbers: list[int] | None
    pointIndex: int | None
    markerColor: ItemOrList[ItemOrList[float | int | str | None]] | None
    markerSize: ItemOrList[ItemOrList[float | int | None,]] | None
    bbox: BBox | None


class Plotly(NoSSRComponent):
    """Display a plotly graph."""

    library = "react-plotly.js@2.6.0"

    lib_dependencies: list[str] = ["plotly.js@3.0.1"]

    tag = "Plot"

    is_default = True

    # The figure to display. This can be a plotly figure or a plotly data json.
    data: Var[Figure]

    # The layout of the graph.
    layout: Var[dict]

    # The template for visual appearance of the graph.
    template: Var[Template]

    # The config of the graph.
    config: Var[dict]

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

    # Fired after the plot is laid out (zoom, pan, etc).
    on_relayout: EventHandler[no_args_event_spec]

    # Fired while the plot is being laid out.
    on_relayouting: EventHandler[no_args_event_spec]

    # Fired after the plot style is changed.
    on_restyle: EventHandler[no_args_event_spec]

    # Fired after the plot is redrawn.
    on_redraw: EventHandler[no_args_event_spec]

    # Fired after selecting plot elements.
    on_selected: EventHandler[_event_points_data_signature]

    # Fired while dragging a selection.
    on_selecting: EventHandler[_event_points_data_signature]

    # Fired while an animation is occurring.
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
        from plotly.graph_objs.layout import Template
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
                    _js_expr=f"{{...mergician({figure!s},"
                    f"{','.join(str(md) for md in merge_dicts)})}}",
                ),
            )
        else:
            # Spread the figure dict over props, nothing to merge.
            tag.special_props.append(Var(_js_expr=f"{figure!s}"))
        return tag


CREATE_PLOTLY_COMPONENT: ImportDict = {
    "react-plotly.js": [
        ImportVar(
            tag="createPlotlyComponent",
            is_default=True,
            package_path="/factory",
        ),
    ]
}


def dynamic_plotly_import(name: str, package: str) -> str:
    """Create a dynamic import for a plotly component.

    Args:
        name: The name of the component.
        package: The package path of the component.

    Returns:
        The dynamic import for the plotly component.
    """
    library_import = f"import('{package}')"
    mod_import = ".then((mod) => ({ default: createPlotlyComponent(mod) }))"
    return f"""
const {name} = ClientSide(lazy(() =>
    {library_import}{mod_import}
))
"""


class PlotlyBasic(Plotly):
    """Display a basic plotly graph."""

    tag: str = "BasicPlotlyPlot"

    library = "react-plotly.js@2.6.0"

    lib_dependencies: list[str] = ["plotly.js-basic-dist-min@3.0.1"]

    def add_imports(self) -> ImportDict | list[ImportDict]:
        """Add imports for the plotly basic component.

        Returns:
            The imports for the plotly basic component.
        """
        return CREATE_PLOTLY_COMPONENT

    def _get_dynamic_imports(self) -> str:
        """Get the dynamic imports for the plotly basic component.

        Returns:
            The dynamic imports for the plotly basic component.
        """
        return dynamic_plotly_import(self.tag, "plotly.js-basic-dist-min")


class PlotlyCartesian(Plotly):
    """Display a plotly cartesian graph."""

    tag: str = "CartesianPlotlyPlot"

    library = "react-plotly.js@2.6.0"

    lib_dependencies: list[str] = ["plotly.js-cartesian-dist-min@3.0.1"]

    def add_imports(self) -> ImportDict | list[ImportDict]:
        """Add imports for the plotly cartesian component.

        Returns:
            The imports for the plotly cartesian component.
        """
        return CREATE_PLOTLY_COMPONENT

    def _get_dynamic_imports(self) -> str:
        """Get the dynamic imports for the plotly cartesian component.

        Returns:
            The dynamic imports for the plotly cartesian component.
        """
        return dynamic_plotly_import(self.tag, "plotly.js-cartesian-dist-min")


class PlotlyGeo(Plotly):
    """Display a plotly geo graph."""

    tag: str = "GeoPlotlyPlot"

    library = "react-plotly.js@2.6.0"

    lib_dependencies: list[str] = ["plotly.js-geo-dist-min@3.0.1"]

    def add_imports(self) -> ImportDict | list[ImportDict]:
        """Add imports for the plotly geo component.

        Returns:
            The imports for the plotly geo component.
        """
        return CREATE_PLOTLY_COMPONENT

    def _get_dynamic_imports(self) -> str:
        """Get the dynamic imports for the plotly geo component.

        Returns:
            The dynamic imports for the plotly geo component.
        """
        return dynamic_plotly_import(self.tag, "plotly.js-geo-dist-min")


class PlotlyGl3d(Plotly):
    """Display a plotly 3d graph."""

    tag: str = "Gl3dPlotlyPlot"

    library = "react-plotly.js@2.6.0"

    lib_dependencies: list[str] = ["plotly.js-gl3d-dist-min@3.0.1"]

    def add_imports(self) -> ImportDict | list[ImportDict]:
        """Add imports for the plotly 3d component.

        Returns:
            The imports for the plotly 3d component.
        """
        return CREATE_PLOTLY_COMPONENT

    def _get_dynamic_imports(self) -> str:
        """Get the dynamic imports for the plotly 3d component.

        Returns:
            The dynamic imports for the plotly 3d component.
        """
        return dynamic_plotly_import(self.tag, "plotly.js-gl3d-dist-min")


class PlotlyGl2d(Plotly):
    """Display a plotly 2d graph."""

    tag: str = "Gl2dPlotlyPlot"

    library = "react-plotly.js@2.6.0"

    lib_dependencies: list[str] = ["plotly.js-gl2d-dist-min@3.0.1"]

    def add_imports(self) -> ImportDict | list[ImportDict]:
        """Add imports for the plotly 2d component.

        Returns:
            The imports for the plotly 2d component.
        """
        return CREATE_PLOTLY_COMPONENT

    def _get_dynamic_imports(self) -> str:
        """Get the dynamic imports for the plotly 2d component.

        Returns:
            The dynamic imports for the plotly 2d component.
        """
        return dynamic_plotly_import(self.tag, "plotly.js-gl2d-dist-min")


class PlotlyMapbox(Plotly):
    """Display a plotly mapbox graph."""

    tag: str = "MapboxPlotlyPlot"

    library = "react-plotly.js@2.6.0"

    lib_dependencies: list[str] = ["plotly.js-mapbox-dist-min@3.0.1"]

    def add_imports(self) -> ImportDict | list[ImportDict]:
        """Add imports for the plotly mapbox component.

        Returns:
            The imports for the plotly mapbox component.
        """
        return CREATE_PLOTLY_COMPONENT

    def _get_dynamic_imports(self) -> str:
        """Get the dynamic imports for the plotly mapbox component.

        Returns:
            The dynamic imports for the plotly mapbox component.
        """
        return dynamic_plotly_import(self.tag, "plotly.js-mapbox-dist-min")


class PlotlyFinance(Plotly):
    """Display a plotly finance graph."""

    tag: str = "FinancePlotlyPlot"

    library = "react-plotly.js@2.6.0"

    lib_dependencies: list[str] = ["plotly.js-finance-dist-min@3.0.1"]

    def add_imports(self) -> ImportDict | list[ImportDict]:
        """Add imports for the plotly finance component.

        Returns:
            The imports for the plotly finance component.
        """
        return CREATE_PLOTLY_COMPONENT

    def _get_dynamic_imports(self) -> str:
        """Get the dynamic imports for the plotly finance component.

        Returns:
            The dynamic imports for the plotly finance component.
        """
        return dynamic_plotly_import(self.tag, "plotly.js-finance-dist-min")


class PlotlyStrict(Plotly):
    """Display a plotly strict graph."""

    tag: str = "StrictPlotlyPlot"

    library = "react-plotly.js@2.6.0"

    lib_dependencies: list[str] = ["plotly.js-strict-dist-min@3.0.1"]

    def add_imports(self) -> ImportDict | list[ImportDict]:
        """Add imports for the plotly strict component.

        Returns:
            The imports for the plotly strict component.
        """
        return CREATE_PLOTLY_COMPONENT

    def _get_dynamic_imports(self) -> str:
        """Get the dynamic imports for the plotly strict component.

        Returns:
            The dynamic imports for the plotly strict component.
        """
        return dynamic_plotly_import(self.tag, "plotly.js-strict-dist-min")
