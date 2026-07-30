"""A module that defines the chart components in Recharts."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, Sequence
from types import SimpleNamespace
from typing import Any, ClassVar, TypedDict, get_args, get_origin

from reflex_base.components.component import Component, field
from reflex_base.components.memo import _MemoComponentWrapper, memo
from reflex_base.constants import EventTriggers
from reflex_base.constants.colors import Color
from reflex_base.event import EventHandler, no_args_event_spec
from reflex_base.vars.base import Var
from reflex_base.vars.object import RestProp
from typing_extensions import NotRequired

from reflex_components_recharts.general import ResponsiveContainer

from .recharts import (
    LiteralAnimationEasing,
    LiteralComposedChartBaseValue,
    LiteralLayout,
    LiteralStackOffset,
    LiteralSyncMethod,
    RechartsCharts,
)


class ChartBase(RechartsCharts):
    """A component that wraps a Recharts charts."""

    width: Var[str | int] = field(
        default=Var.create("100%"),
        doc="The width of chart container. String or Integer",
    )

    height: Var[str | int] = field(
        default=Var.create("100%"), doc="The height of chart container."
    )

    on_click: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of click on the component in this chart"
    )

    on_mouse_enter: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseenter on the component in this chart"
    )

    on_mouse_move: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mousemove on the component in this chart"
    )

    on_mouse_leave: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseleave on the component in this chart"
    )

    @staticmethod
    def _ensure_valid_dimension(name: str, value: Any) -> None:
        """Ensure that the value is an int type or str percentage.

        Unfortunately str Vars cannot be checked and are implicitly not allowed.

        Args:
            name: The name of the prop.
            value: The value to check.

        Raises:
            ValueError: If the value is not an int type or str percentage.
        """
        if value is None:
            return
        if isinstance(value, int):
            return
        if isinstance(value, str) and value.endswith("%"):
            return
        if isinstance(value, Var) and issubclass(value._var_type, int):
            return
        msg = (
            f"Chart {name} must be specified as int pixels or percentage, not {value!r}. "
            "CSS unit dimensions are allowed on parent container."
        )
        raise ValueError(msg)

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a chart component.

        Args:
            *children: The children of the chart component.
            **props: The properties of the chart component.

        Returns:
            The chart component wrapped in a responsive container.
        """
        width = props.pop("width", None)
        height = props.pop("height", None)
        cls._ensure_valid_dimension("width", width)
        cls._ensure_valid_dimension("height", height)

        # Ensure that the min_height and min_width are set to prevent the chart from collapsing.
        # We are using small values so that height and width can still be used over min_height and min_width.
        # Without this, sometimes the chart will not be visible. Causing confusion to the user.
        # With this, the user will see a small chart and can adjust the height and width and can figure out that the issue is with the size.
        min_height = props.pop("min_height", 10)
        min_width = props.pop("min_width", 10)

        return ResponsiveContainer.create(
            super().create(*children, **props),
            width=width if width is not None else "100%",
            height=height if height is not None else "100%",
            min_width=min_width,
            min_height=min_height,
        )


class CategoricalChartBase(ChartBase):
    """A component that wraps a Categorical Recharts charts."""

    data: Var[Sequence[dict[str, Any]]] = field(
        doc="The source data, in which each element is an object."
    )

    margin: Var[dict[str, Any]] = field(
        doc='The sizes of whitespace around the chart, i.e. {"top": 50, "right": 30, "left": 20, "bottom": 5}.'
    )

    sync_id: Var[str] = field(
        doc="If any two categorical charts(rx.line_chart, rx.area_chart, rx.bar_chart, rx.composed_chart) have the same sync_id, these two charts can sync the position GraphingTooltip, and the start_index, end_index of Brush."
    )

    sync_method: Var[LiteralSyncMethod] = field(
        doc="When sync_id is provided, allows customisation of how the charts will synchronize GraphingTooltips and brushes. Using 'index' (default setting), other charts will reuse current datum's index within the data array. In cases where data does not have the same length, this might yield unexpected results. In that case use 'value' which will try to match other charts values, or a fully custom function which will receive tick, data as argument and should return an index. 'index' | 'value' | function. Default: \"index\""
    )

    layout: Var[LiteralLayout] = field(
        doc="The layout of area in the chart. 'horizontal' | 'vertical'. Default: \"horizontal\""
    )

    stack_offset: Var[LiteralStackOffset] = field(
        doc="The type of offset function used to generate the lower and upper values in the series array. The four types are built-in offsets in d3-shape. 'expand' | 'none' | 'wiggle' | 'silhouette'"
    )


class AreaChart(CategoricalChartBase):
    """An Area chart component in Recharts."""

    tag = "AreaChart"

    alias = "RechartsAreaChart"

    base_value: Var[int | LiteralComposedChartBaseValue] = field(
        doc="The base value of area. Number | 'dataMin' | 'dataMax' | 'auto'. Default: \"auto\""
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = [
        "XAxis",
        "YAxis",
        "ReferenceArea",
        "ReferenceDot",
        "ReferenceLine",
        "Brush",
        "CartesianGrid",
        "Legend",
        "GraphingTooltip",
        "Area",
        "Defs",
    ]


class BarChart(CategoricalChartBase):
    """A Bar chart component in Recharts."""

    tag = "BarChart"

    alias = "RechartsBarChart"

    bar_category_gap: Var[str | int] = field(
        doc='The gap between two bar categories, which can be a percent value or a fixed value. Percentage | Number. Default: "10%"'
    )

    bar_gap: Var[str | int] = field(
        doc="The gap between two bars in the same category, which can be a percent value or a fixed value. Percentage | Number. Default: 4"
    )

    bar_size: Var[int] = field(doc="The width of all the bars in the chart. Number")

    max_bar_size: Var[int] = field(
        doc="The maximum width of all the bars in a horizontal BarChart, or maximum height in a vertical BarChart."
    )

    stack_offset: Var[LiteralStackOffset] = field(
        doc='The type of offset function used to generate the lower and upper values in the series array. The four types are built-in offsets in d3-shape. Default: "none"'
    )

    reverse_stack_order: Var[bool] = field(
        doc="If false set, stacked items will be rendered left to right. If true set, stacked items will be rendered right to left. (Render direction affects SVG layering, not x position.) Default: False"
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = [
        "XAxis",
        "YAxis",
        "ReferenceArea",
        "ReferenceDot",
        "ReferenceLine",
        "Brush",
        "CartesianGrid",
        "Legend",
        "GraphingTooltip",
        "Bar",
        "Defs",
    ]


class LineChart(CategoricalChartBase):
    """A Line chart component in Recharts."""

    tag = "LineChart"

    alias = "RechartsLineChart"

    # Valid children components
    _valid_children: ClassVar[list[str]] = [
        "XAxis",
        "YAxis",
        "ReferenceArea",
        "ReferenceDot",
        "ReferenceLine",
        "Brush",
        "CartesianGrid",
        "Legend",
        "GraphingTooltip",
        "Line",
        "Defs",
    ]


class ComposedChart(CategoricalChartBase):
    """A Composed chart component in Recharts."""

    tag = "ComposedChart"

    alias = "RechartsComposedChart"

    base_value: Var[int | LiteralComposedChartBaseValue] = field(
        doc="The base value of area. Number | 'dataMin' | 'dataMax' | 'auto'. Default: \"auto\""
    )

    bar_category_gap: Var[str | int] = field(
        doc='The gap between two bar categories, which can be a percent value or a fixed value. Percentage | Number. Default: "10%"'
    )

    bar_gap: Var[int] = field(
        doc="The gap between two bars in the same category. Default: 4"
    )

    bar_size: Var[int] = field(
        doc="The width or height of each bar. If the barSize is not specified, the size of the bar will be calculated by the barCategoryGap, barGap and the quantity of bar groups."
    )

    reverse_stack_order: Var[bool] = field(
        doc="If false set, stacked items will be rendered left to right. If true set, stacked items will be rendered right to left. (Render direction affects SVG layering, not x position). Default: False"
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = [
        "XAxis",
        "YAxis",
        "ReferenceArea",
        "ReferenceDot",
        "ReferenceLine",
        "Brush",
        "CartesianGrid",
        "Legend",
        "GraphingTooltip",
        "Area",
        "Line",
        "Bar",
        "Defs",
    ]


class PieChart(ChartBase):
    """A Pie chart component in Recharts."""

    tag = "PieChart"

    alias = "RechartsPieChart"

    margin: Var[dict[str, Any]] = field(
        doc='The sizes of whitespace around the chart, i.e. {"top": 50, "right": 30, "left": 20, "bottom": 5}.'
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = [
        "PolarAngleAxis",
        "PolarRadiusAxis",
        "PolarGrid",
        "Legend",
        "GraphingTooltip",
        "Pie",
        "Defs",
    ]

    on_mouse_down: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mousedown on the sectors in this group"
    )

    on_mouse_up: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseup on the sectors in this group"
    )

    on_mouse_over: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseover on the sectors in this group"
    )

    on_mouse_out: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseout on the sectors in this group"
    )


class RadarChart(ChartBase):
    """A Radar chart component in Recharts."""

    tag = "RadarChart"

    alias = "RechartsRadarChart"

    data: Var[Sequence[dict[str, Any]]] = field(
        doc="The source data, in which each element is an object."
    )

    margin: Var[dict[str, Any]] = field(
        doc='The sizes of whitespace around the chart, i.e. {"top": 50, "right": 30, "left": 20, "bottom": 5}. Default: {"top": 0, "right": 0, "left": 0, "bottom": 0}'
    )

    cx: Var[int | str] = field(
        doc='The The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of width. Number | Percentage. Default: "50%"'
    )

    cy: Var[int | str] = field(
        doc='The The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of height. Number | Percentage. Default: "50%"'
    )

    start_angle: Var[int] = field(
        doc="The angle of first radial direction line. Default: 90"
    )

    end_angle: Var[int] = field(
        doc="The angle of last point in the circle which should be startAngle - 360 or startAngle + 360. We'll calculate the direction of chart by 'startAngle' and 'endAngle'. Default: -270"
    )

    inner_radius: Var[int | str] = field(
        doc="The inner radius of first circle grid. If set a percentage, the final value is obtained by multiplying the percentage of maxRadius which is calculated by the width, height, cx, cy. Number | Percentage. Default: 0"
    )

    outer_radius: Var[int | str] = field(
        doc='The outer radius of last circle grid. If set a percentage, the final value is obtained by multiplying the percentage of maxRadius which is calculated by the width, height, cx, cy. Number | Percentage. Default: "80%"'
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = [
        "PolarAngleAxis",
        "PolarRadiusAxis",
        "PolarGrid",
        "Legend",
        "GraphingTooltip",
        "Radar",
        "Defs",
    ]

    @classmethod
    def get_event_triggers(cls) -> dict[str, Var | Any]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            EventTriggers.ON_CLICK: no_args_event_spec,
            EventTriggers.ON_MOUSE_ENTER: no_args_event_spec,
            EventTriggers.ON_MOUSE_LEAVE: no_args_event_spec,
        }


class RadialBarChart(ChartBase):
    """A RadialBar chart component in Recharts."""

    tag = "RadialBarChart"

    alias = "RechartsRadialBarChart"

    data: Var[Sequence[dict[str, Any]]] = field(
        doc="The source data which each element is an object."
    )

    margin: Var[dict[str, Any]] = field(
        doc='The sizes of whitespace around the chart. Default: {"top": 5, "right": 5, "left": 5 "bottom": 5}'
    )

    cx: Var[int | str] = field(
        doc='The The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of width. Number | Percentage. Default: "50%"'
    )

    cy: Var[int | str] = field(
        doc='The The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of height. Number | Percentage. Default: "50%"'
    )

    start_angle: Var[int] = field(
        doc="The angle of first radial direction line. Default: 0"
    )

    end_angle: Var[int] = field(
        doc="The angle of last point in the circle which should be startAngle - 360 or startAngle + 360. We'll calculate the direction of chart by 'startAngle' and 'endAngle'. Default: 360"
    )

    inner_radius: Var[int | str] = field(
        doc='The inner radius of first circle grid. If set a percentage, the final value is obtained by multiplying the percentage of maxRadius which is calculated by the width, height, cx, cy. Number | Percentage. Default: "30%"'
    )

    outer_radius: Var[int | str] = field(
        doc='The outer radius of last circle grid. If set a percentage, the final value is obtained by multiplying the percentage of maxRadius which is calculated by the width, height, cx, cy. Number | Percentage. Default: "100%"'
    )

    bar_category_gap: Var[int | str] = field(
        doc='The gap between two bar categories, which can be a percent value or a fixed value. Percentage | Number. Default: "10%"'
    )

    bar_gap: Var[str] = field(
        doc="The gap between two bars in the same category, which can be a percent value or a fixed value. Percentage | Number. Default: 4"
    )

    bar_size: Var[int] = field(
        doc="The size of each bar. If the barSize is not specified, the size of bar will be calculated by the barCategoryGap, barGap and the quantity of bar groups."
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = [
        "PolarAngleAxis",
        "PolarRadiusAxis",
        "PolarGrid",
        "Legend",
        "GraphingTooltip",
        "RadialBar",
        "Defs",
    ]


class ScatterChart(ChartBase):
    """A Scatter chart component in Recharts."""

    tag = "ScatterChart"

    alias = "RechartsScatterChart"

    margin: Var[dict[str, Any]] = field(
        doc='The sizes of whitespace around the chart. Default: {"top": 5, "right": 5, "bottom": 5, "left": 5}'
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = [
        "XAxis",
        "YAxis",
        "ZAxis",
        "ReferenceArea",
        "ReferenceDot",
        "ReferenceLine",
        "Brush",
        "CartesianGrid",
        "Legend",
        "GraphingTooltip",
        "Scatter",
        "Defs",
    ]

    @classmethod
    def get_event_triggers(cls) -> dict[str, Var | Any]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            EventTriggers.ON_CLICK: no_args_event_spec,
            EventTriggers.ON_MOUSE_DOWN: no_args_event_spec,
            EventTriggers.ON_MOUSE_UP: no_args_event_spec,
            EventTriggers.ON_MOUSE_MOVE: no_args_event_spec,
            EventTriggers.ON_MOUSE_OVER: no_args_event_spec,
            EventTriggers.ON_MOUSE_OUT: no_args_event_spec,
            EventTriggers.ON_MOUSE_ENTER: no_args_event_spec,
            EventTriggers.ON_MOUSE_LEAVE: no_args_event_spec,
        }


class FunnelChart(ChartBase):
    """A Funnel chart component in Recharts."""

    tag = "FunnelChart"

    alias = "RechartsFunnelChart"

    layout: Var[str] = field(doc='The layout of bars in the chart. Default: "centric"')

    margin: Var[dict[str, Any]] = field(
        doc='The sizes of whitespace around the chart. Default: {"top": 5, "right": 5, "bottom": 5, "left": 5}'
    )

    stroke: Var[str | Color] = field(
        doc="The stroke color of each bar. String | Object"
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = [
        "Legend",
        "GraphingTooltip",
        "Funnel",
        "Defs",
    ]


class SankeyNode(TypedDict):
    """A node in a Sankey chart."""

    name: str
    type: NotRequired[str]
    fill: NotRequired[str | Color]
    stroke: NotRequired[str | Color]
    strokeWidth: NotRequired[int | float]
    strokeOpacity: NotRequired[int | float]


class SankeyLink(TypedDict):
    """A weighted link between two Sankey chart nodes."""

    source: int
    target: int
    value: int | float
    fill: NotRequired[str | Color]
    fillOpacity: NotRequired[int | float]
    stroke: NotRequired[str | Color]
    strokeWidth: NotRequired[int | float]
    strokeOpacity: NotRequired[int | float]


class SankeyData(TypedDict):
    """The source data for a Sankey chart."""

    nodes: Sequence[SankeyNode]
    links: Sequence[SankeyLink]


class SankeyNodePayload(TypedDict):
    """The payload for a Sankey chart node."""

    name: str
    sourceNodes: list[int]
    sourceLinks: list[int]
    targetLinks: list[int]
    targetNodes: list[int]
    value: int | float
    depth: int
    x: int | float
    dx: int | float
    y: int | float
    dy: int | float


class SankeyNodeProps(TypedDict):
    """The props for a custom Sankey chart node."""

    height: int
    width: int
    payload: SankeyNodePayload
    index: int
    x: int
    y: int


class SankeyLinkPayload(TypedDict):
    """The payload for a Sankey chart link."""

    source: int
    target: int
    value: int | float
    index: int
    width: int | float
    sy: int | float
    ty: int | float


class SankeyLinkProps(TypedDict):
    """The props for a custom Sankey chart link."""

    sourceX: int
    targetX: int
    sourceY: int
    targetY: int
    sourceControlX: int
    targetControlX: int
    sourceRelativeY: int
    targetRelativeY: int
    linkWidth: int
    index: int
    payload: SankeyLinkPayload


def sankey_node(
    fn: Callable,
) -> _MemoComponentWrapper:
    """A decorator to create a custom Sankey chart node.

    Args:
        fn: A function that takes a SankeyNodeProps and returns a Reflex component.

    Returns:
        A function that takes a SankeyNodeProps and returns a Reflex component.
    """
    sig = inspect.signature(fn)
    if (
        len(sig.parameters) != 1
        or (first_param := sig.parameters[next(iter(sig.parameters))]) is None
        or get_origin(first_param.annotation) is not Var
        or not (args := get_args(first_param.annotation))
        or args[0] is not SankeyNodeProps
    ):
        msg = f"@sankey_node decorated function must take a single argument of type SankeyNodeProps, got {sig.parameters}"
        raise TypeError(msg)

    def _wrapper(rest: RestProp) -> Component:
        return fn(**{first_param.name: rest.to(SankeyNodeProps)})

    _wrapper.__name__ = fn.__name__
    _wrapper.__module__ = fn.__module__
    return memo(wrapper=None)(_wrapper)


def sankey_link(
    fn: Callable,
) -> _MemoComponentWrapper:
    """A decorator to create a custom Sankey chart link.

    Args:
        fn: A function that takes a SankeyLinkProps and returns a Reflex component.

    Returns:
        A function that takes a SankeyLinkProps and returns a Reflex component.
    """
    sig = inspect.signature(fn)
    if (
        len(sig.parameters) != 1
        or (first_param := sig.parameters[next(iter(sig.parameters))]) is None
        or get_origin(first_param.annotation) is not Var
        or not (args := get_args(first_param.annotation))
        or args[0] is not SankeyLinkProps
    ):
        msg = f"@sankey_link decorated function must take a single argument of type SankeyLinkProps, got {sig.parameters}"
        raise TypeError(msg)

    def _wrapper(rest: RestProp) -> Component:
        return fn(**{first_param.name: rest.to(SankeyLinkProps)})

    _wrapper.__name__ = fn.__name__
    _wrapper.__module__ = fn.__module__
    return memo(wrapper=None)(_wrapper)


class SankeyChart(ChartBase):
    """A Sankey chart component in Recharts."""

    tag = "Sankey"

    alias = "RechartsSankeyChart"

    name_key: Var[str] = field(doc='The key of each node name. Default: "name"')

    data_key: Var[str | int] = field(doc='The key of each link value. Default: "value"')

    data: Var[SankeyData | Mapping[str, Any]] = field(
        doc="The source data, including nodes and the weighted links between them."
    )

    margin: Var[dict[str, Any]] = field(
        doc='The sizes of whitespace around the chart. Default: {"top": 5, "right": 5, "bottom": 5, "left": 5}'
    )

    node: Var[Any] = field(
        doc="The configuration object or custom renderer used to draw nodes."
    )

    link: Var[Any] = field(
        doc="The configuration object or custom renderer used to draw links."
    )

    sort: Var[bool] = field(
        doc="Whether to sort nodes on the y-axis or display them in data order."
    )

    node_padding: Var[int] = field(doc="The padding between nodes.")

    node_width: Var[int] = field(doc="The width of each node.")

    link_curvature: Var[float] = field(doc="The curvature of each link.")

    iterations: Var[int] = field(
        doc="The number of layout iterations used to position nodes and links."
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = [
        "Legend",
        "GraphingTooltip",
        "Defs",
    ]


class SankeyNamespace(SimpleNamespace):
    """A namespace for the Sankey chart components."""

    node = staticmethod(sankey_node)
    link = staticmethod(sankey_link)
    __call__ = staticmethod(SankeyChart.create)

    # For type checking
    SankeyNode = SankeyNode
    SankeyLink = SankeyLink
    SankeyData = SankeyData
    SankeyNodePayload = SankeyNodePayload
    SankeyNodeProps = SankeyNodeProps
    SankeyLinkPayload = SankeyLinkPayload
    SankeyLinkProps = SankeyLinkProps


class Treemap(RechartsCharts):
    """A Treemap chart component in Recharts."""

    tag = "Treemap"

    alias = "RechartsTreemap"

    width: Var[str | int] = field(
        default=Var.create("100%"),
        doc='The width of chart container. String or Integer. Default: "100%"',
    )

    height: Var[str | int] = field(
        default=Var.create("100%"),
        doc='The height of chart container. String or Integer. Default: "100%"',
    )

    data: Var[Sequence[dict[str, Any]]] = field(doc="data of treemap. Array")

    data_key: Var[str | int] = field(
        doc='The key of a group of data which should be unique in a treemap. String | Number. Default: "value"'
    )

    name_key: Var[str] = field(
        doc='The key of each sector\'s name. String. Default: "name"'
    )

    aspect_ratio: Var[int] = field(
        doc="The treemap will try to keep every single rectangle's aspect ratio near the aspectRatio given. Number"
    )

    is_animation_active: Var[bool] = field(
        doc="If set false, animation of area will be disabled. Default: True"
    )

    animation_begin: Var[int] = field(
        doc="Specifies when the animation should begin, the unit of this option is ms. Default: 0"
    )

    animation_duration: Var[int] = field(
        doc="Specifies the duration of animation, the unit of this option is ms. Default: 1500"
    )

    animation_easing: Var[LiteralAnimationEasing] = field(
        doc="The type of easing function. 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'linear'. Default: \"ease\""
    )

    on_animation_start: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of animation start"
    )

    on_animation_end: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of animation end"
    )

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a chart component.

        Args:
            *children: The children of the chart component.
            **props: The properties of the chart component.

        Returns:
            The Treemap component wrapped in a responsive container.
        """
        return ResponsiveContainer.create(
            super().create(*children, **props),
            width=props.pop("width", "100%"),
            height=props.pop("height", "100%"),
        )


area_chart = AreaChart.create
bar_chart = BarChart.create
line_chart = LineChart.create
composed_chart = ComposedChart.create
pie_chart = PieChart.create
radar_chart = RadarChart.create
radial_bar_chart = RadialBarChart.create
scatter_chart = ScatterChart.create
funnel_chart = FunnelChart.create
sankey_chart = SankeyNamespace()
treemap = Treemap.create
