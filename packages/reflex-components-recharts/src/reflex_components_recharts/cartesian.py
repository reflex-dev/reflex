"""Cartesian charts in Recharts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar, TypedDict

from reflex_base.components.component import field
from reflex_base.constants import EventTriggers
from reflex_base.constants.colors import Color
from reflex_base.event import EventHandler, no_args_event_spec
from reflex_base.vars.base import LiteralVar, Var

from .recharts import (
    ACTIVE_DOT_TYPE,
    LiteralAnimationEasing,
    LiteralCurveType,
    LiteralDirection,
    LiteralIfOverflow,
    LiteralInterval,
    LiteralIntervalAxis,
    LiteralLayout,
    LiteralLegendType,
    LiteralLineType,
    LiteralOrientationLeftRight,
    LiteralOrientationTopBottom,
    LiteralOrientationTopBottomLeftRight,
    LiteralPolarRadiusType,
    LiteralScale,
    LiteralShape,
    LiteralTextAnchor,
    Recharts,
)


class Axis(Recharts):
    """A base class for axes in Recharts."""

    data_key: Var[str | int] = field(doc="The key of data displayed in the axis.")

    hide: Var[bool] = field(
        doc="If set true, the axis do not display in the chart. Default: False"
    )

    width: Var[str | int] = field(
        doc="The width of axis which is usually calculated internally."
    )

    height: Var[str | int] = field(doc="The height of axis, which can be set by user.")

    type_: Var[LiteralPolarRadiusType] = field(
        doc="The type of axis 'number' | 'category'"
    )

    interval: Var[LiteralIntervalAxis | int] = field(
        doc='If set 0, all the ticks will be shown. If set preserveStart", "preserveEnd" or "preserveStartEnd", the ticks which is to be shown or hidden will be calculated automatically. Default: "preserveEnd"'
    )

    allow_decimals: Var[bool] = field(
        doc="Allow the ticks of Axis to be decimals or not. Default: True"
    )

    allow_data_overflow: Var[bool] = field(
        doc="When domain of the axis is specified and the type of the axis is 'number', if allowDataOverflow is set to be false, the domain will be adjusted when the minimum value of data is smaller than domain[0] or the maximum value of data is greater than domain[1] so that the axis displays all data values. If set to true, graphic elements (line, area, bars) will be clipped to conform to the specified domain. Default: False"
    )

    allow_duplicated_category: Var[bool] = field(
        doc='Allow the axis has duplicated categorys or not when the type of axis is "category". Default: True'
    )

    domain: Var[Sequence] = field(
        doc='The range of the axis. Work best in conjunction with allow_data_overflow. Default: [0, "auto"]'
    )

    axis_line: Var[bool] = field(
        doc="If set false, no axis line will be drawn. Default: True"
    )

    mirror: Var[bool] = field(
        doc="If set true, flips ticks around the axis line, displaying the labels inside the chart instead of outside. Default: False"
    )

    reversed: Var[bool] = field(doc="Reverse the ticks or not. Default: False")

    label: Var[str | int | dict[str, Any]] = field(
        doc="The label of axis, which appears next to the axis."
    )

    scale: Var[LiteralScale] = field(
        doc="If 'auto' set, the scale function is decided by the type of chart, and the props type. 'auto' | 'linear' | 'pow' | 'sqrt' | 'log' | 'identity' | 'time' | 'band' | 'point' | 'ordinal' | 'quantile' | 'quantize' | 'utc' | 'sequential' | 'threshold'. Default: \"auto\""
    )

    unit: Var[str | int] = field(
        doc="The unit of data displayed in the axis. This option will be used to represent an index unit in a scatter chart."
    )

    name: Var[str | int] = field(
        doc="The name of data displayed in the axis. This option will be used to represent an index in a scatter chart."
    )

    ticks: Var[Sequence[str | int]] = field(
        doc="Set the values of axis ticks manually."
    )

    tick: Var[bool | dict] = field(doc="If set false, no ticks will be drawn.")

    tick_count: Var[int] = field(
        doc="The count of axis ticks. Not used if 'type' is 'category'. Default: 5"
    )

    tick_line: Var[bool] = field(
        doc="If set false, no axis tick lines will be drawn. Default: True"
    )

    tick_size: Var[int] = field(doc="The length of tick line. Default: 6")

    min_tick_gap: Var[int] = field(
        doc="The minimum gap between two adjacent labels. Default: 5"
    )

    stroke: Var[str | Color] = field(
        default=LiteralVar.create(Color("gray", 9)),
        doc='The stroke color of axis. Default: rx.color("gray", 9)',
    )

    text_anchor: Var[LiteralTextAnchor] = field(
        doc='The text anchor of axis. Default: "middle"'
    )

    on_click: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of click on the ticks of this axis"
    )

    on_mouse_down: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mousedown on the ticks of this axis"
    )

    on_mouse_up: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseup on the ticks of this axis"
    )

    on_mouse_move: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mousemove on the ticks of this axis"
    )

    on_mouse_out: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseout on the ticks of this axis"
    )

    on_mouse_enter: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseenter on the ticks of this axis"
    )

    on_mouse_leave: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseleave on the ticks of this axis"
    )


class XAxis(Axis):
    """An XAxis component in Recharts."""

    tag = "XAxis"

    alias = "RechartsXAxis"

    orientation: Var[LiteralOrientationTopBottom] = field(
        doc="The orientation of axis 'top' | 'bottom'. Default: \"bottom\""
    )

    x_axis_id: Var[str | int] = field(
        doc="The id of x-axis which is corresponding to the data. Default: 0"
    )

    include_hidden: Var[bool] = field(
        doc="Ensures that all datapoints within a chart contribute to its domain calculation, even when they are hidden. Default: False"
    )

    angle: Var[int] = field(doc="The angle of axis ticks. Default: 0")

    padding: Var[dict[str, int]] = field(
        doc='Specify the padding of x-axis. Default: {"left": 0, "right": 0}'
    )


class YAxis(Axis):
    """A YAxis component in Recharts."""

    tag = "YAxis"

    alias = "RechartsYAxis"

    orientation: Var[LiteralOrientationLeftRight] = field(
        doc="The orientation of axis 'left' | 'right'. Default: \"left\""
    )

    y_axis_id: Var[str | int] = field(
        doc="The id of y-axis which is corresponding to the data. Default: 0"
    )

    padding: Var[dict[str, int]] = field(
        doc='Specify the padding of y-axis. Default: {"top": 0, "bottom": 0}'
    )


class ZAxis(Recharts):
    """A ZAxis component in Recharts."""

    tag = "ZAxis"

    alias = "RechartsZAxis"

    data_key: Var[str | int] = field(doc="The key of data displayed in the axis.")

    z_axis_id: Var[str | int] = field(doc="The unique id of z-axis. Default: 0")

    range: Var[Sequence[int]] = field(
        default=LiteralVar.create([60, 400]),
        doc="The range of axis. Default: [60, 400]",
    )

    unit: Var[str | int] = field(
        doc="The unit of data displayed in the axis. This option will be used to represent an index unit in a scatter chart."
    )

    name: Var[str | int] = field(
        doc="The name of data displayed in the axis. This option will be used to represent an index in a scatter chart."
    )

    scale: Var[LiteralScale] = field(
        doc="If 'auto' set, the scale function is decided by the type of chart, and the props type. Default: \"auto\""
    )


class Brush(Recharts):
    """A Brush component in Recharts."""

    tag = "Brush"

    alias = "RechartsBrush"

    stroke: Var[str | Color] = field(
        default=LiteralVar.create(Color("gray", 9)),
        doc='Stroke color. Default: rx.color("gray", 9)',
    )

    fill: Var[str | Color] = field(
        default=LiteralVar.create(Color("gray", 2)),
        doc='The fill color of brush. Default: rx.color("gray", 2)',
    )

    data_key: Var[str | int] = field(doc="The key of data displayed in the axis.")

    x: Var[int] = field(doc="The x-coordinate of brush. Default: 0")

    y: Var[int] = field(doc="The y-coordinate of brush. Default: 0")

    width: Var[int] = field(doc="The width of brush. Default: 0")

    height: Var[int] = field(doc="The height of brush. Default: 40")

    data: Var[Sequence[Any]] = field(
        doc="The original data of a LineChart, a BarChart or an AreaChart."
    )

    traveller_width: Var[int] = field(doc="The width of each traveller. Default: 5")

    gap: Var[int] = field(
        doc="The data with gap of refreshing chart. If the option is not set, the chart will be refreshed every time. Default: 1"
    )

    start_index: Var[int] = field(
        doc="The default start index of brush. If the option is not set, the start index will be 0. Default: 0"
    )

    end_index: Var[int] = field(
        doc="The default end index of brush. If the option is not set, the end index will be calculated by the length of data."
    )

    @classmethod
    def get_event_triggers(cls) -> dict[str, Var | Any]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            EventTriggers.ON_CHANGE: no_args_event_spec,
        }


class Cartesian(Recharts):
    """A base class for cartesian charts in Recharts."""

    layout: Var[LiteralLayout] = field(
        doc="The layout of bar in the chart, usually inherited from parent. 'horizontal' | 'vertical'"
    )

    data_key: Var[str | int] = field(
        doc="The key of a group of data which should be unique in an area chart."
    )

    x_axis_id: Var[str | int] = field(
        doc="The id of x-axis which is corresponding to the data. Default: 0"
    )

    y_axis_id: Var[str | int] = field(
        doc="The id of y-axis which is corresponding to the data. Default: 0"
    )

    legend_type: Var[LiteralLegendType] = field(
        doc="The type of icon in legend. If set to 'none', no legend item will be rendered. 'line' | 'plainline' | 'square' | 'rect'| 'circle' | 'cross' | 'diamond' | 'star' | 'triangle' | 'wye' | 'none' optional"
    )

    label: Var[bool | dict[str, Any]] = field(
        doc="If false set, labels will not be drawn. If true set, labels will be drawn which have the props calculated internally. Default: False"
    )

    is_animation_active: Var[bool] = field(
        doc="If set false, animation of bar will be disabled. Default: True"
    )

    animation_begin: Var[int] = field(
        doc="Specifies when the animation should begin, the unit of this option is ms. Default: 0"
    )

    animation_duration: Var[int] = field(
        doc="Specifies the duration of animation, the unit of this option is ms. Default: 1500"
    )

    animation_easing: Var[LiteralAnimationEasing] = field(
        doc='The type of easing function. Default: "ease"'
    )

    unit: Var[str | int] = field(
        doc="The unit of data. This option will be used in tooltip."
    )

    name: Var[str | int] = field(
        doc="The name of data. This option will be used in tooltip and legend to represent the component. If no value was set to this option, the value of dataKey will be used alternatively."
    )

    on_animation_start: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of animation start"
    )

    on_animation_end: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of animation end"
    )

    on_click: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of click on the component in this group"
    )

    on_mouse_down: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mousedown on the component in this group"
    )

    on_mouse_up: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseup on the component in this group"
    )

    on_mouse_move: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mousemove on the component in this group"
    )

    on_mouse_over: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseover on the component in this group"
    )

    on_mouse_out: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseout on the component in this group"
    )

    on_mouse_enter: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseenter on the component in this group"
    )

    on_mouse_leave: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseleave on the component in this group"
    )


class Area(Cartesian):
    """An Area component in Recharts."""

    tag = "Area"

    alias = "RechartsArea"

    stroke: Var[str | Color] = field(
        default=LiteralVar.create(Color("accent", 9)),
        doc='The color of the line stroke. Default: rx.color("accent", 9)',
    )

    stroke_width: Var[str | int | float] = field(
        doc="The width of the line stroke. Default: 1"
    )

    fill: Var[str | Color] = field(
        default=LiteralVar.create(Color("accent", 5)),
        doc='The color of the area fill. Default: rx.color("accent", 5)',
    )

    type_: Var[LiteralCurveType] = field(
        default=LiteralVar.create("monotone"),
        doc="The interpolation type of area. And customized interpolation function can be set to type. 'basis' | 'basisClosed' | 'basisOpen' | 'bumpX' | 'bumpY' | 'bump' | 'linear' | 'linearClosed' | 'natural' | 'monotoneX' | 'monotoneY' | 'monotone' | 'step' | 'stepBefore' | 'stepAfter'. Default: \"monotone\"",
    )

    dot: Var[ACTIVE_DOT_TYPE] = field(
        doc="If false set, dots will not be drawn. If true set, dots will be drawn which have the props calculated internally. Default: False"
    )

    active_dot: Var[ACTIVE_DOT_TYPE] = field(
        default=LiteralVar.create({
            "stroke": Color("accent", 2),
            "fill": Color("accent", 10),
        }),
        doc='The dot is shown when user enter an area chart and this chart has tooltip. If false set, no active dot will not be drawn. If true set, active dot will be drawn which have the props calculated internally. Default: {stroke: rx.color("accent", 2), fill: rx.color("accent", 10)}',
    )

    base_line: Var[int | Sequence[dict[str, Any]]] = field(
        doc="The value which can describle the line, usually calculated internally."
    )

    points: Var[Sequence[dict[str, Any]]] = field(
        doc="The coordinates of all the points in the area, usually calculated internally."
    )

    stack_id: Var[str | int] = field(
        doc="The stack id of area, when two areas have the same value axis and same stack_id, then the two areas are stacked in order."
    )

    connect_nulls: Var[bool] = field(
        doc="Whether to connect a graph area across null points. Default: False"
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = ["LabelList"]


class Bar(Cartesian):
    """A Bar component in Recharts."""

    tag = "Bar"

    alias = "RechartsBar"

    stroke: Var[str | Color] = field(doc="The color of the line stroke.")

    stroke_width: Var[str | int | float] = field(doc="The width of the line stroke.")

    fill: Var[str | Color] = field(
        default=LiteralVar.create(Color("accent", 9)),
        doc='The width of the line stroke. Default: Color("accent", 9)',
    )

    background: Var[bool] = field(
        doc="If false set, background of bars will not be drawn. If true set, background of bars will be drawn which have the props calculated internally. Default: False"
    )

    stack_id: Var[str] = field(
        doc="The stack id of bar, when two bars have the same value axis and same stack_id, then the two bars are stacked in order."
    )

    unit: Var[str | int] = field(
        doc="The unit of data. This option will be used in tooltip."
    )

    min_point_size: Var[int] = field(
        doc="The minimal height of a bar in a horizontal BarChart, or the minimal width of a bar in a vertical BarChart. By default, 0 values are not shown. To visualize a 0 (or close to zero) point, set the minimal point size to a pixel value like 3. In stacked bar charts, minPointSize might not be respected for tightly packed values. So we strongly recommend not using this prop in stacked BarCharts."
    )

    name: Var[str | int] = field(
        doc="The name of data. This option will be used in tooltip and legend to represent a bar. If no value was set to this option, the value of dataKey will be used alternatively."
    )

    bar_size: Var[int] = field(
        doc="Size of the bar (if one bar_size is set then a bar_size must be set for all bars)"
    )

    max_bar_size: Var[int] = field(doc="Max size of the bar")

    radius: Var[int | Sequence[int]] = field(
        doc="If set a value, the option is the radius of all the rounded corners. If set a array, the option are in turn the radiuses of top-left corner, top-right corner, bottom-right corner, bottom-left corner. Default: 0"
    )

    # The active bar is shown when a user enters a bar chart and this chart has tooltip. If set to false, no active bar will be drawn. If set to true, active bar will be drawn with the props calculated internally. If passed an object, active bar will be drawn, and the internally calculated props will be merged with the key value pairs of the passed object.
    # active_bar: Var[Union[bool, dict[str, Any]]] #noqa: ERA001

    # Valid children components
    _valid_children: ClassVar[list[str]] = ["Cell", "LabelList", "ErrorBar"]


class Line(Cartesian):
    """A Line component in Recharts."""

    tag = "Line"

    alias = "RechartsLine"

    type_: Var[LiteralCurveType] = field(
        doc="The interpolation type of line. And customized interpolation function can be set to type. It's the same as type in Area."
    )

    stroke: Var[str | Color] = field(
        default=LiteralVar.create(Color("accent", 9)),
        doc='The color of the line stroke. Default: rx.color("accent", 9)',
    )

    stroke_width: Var[str | int | float] = field(
        doc="The width of the line stroke. Default: 1"
    )

    dot: Var[ACTIVE_DOT_TYPE] = field(
        default=LiteralVar.create({
            "stroke": Color("accent", 10),
            "fill": Color("accent", 4),
        }),
        doc='The dot is shown when mouse enter a line chart and this chart has tooltip. If false set, no active dot will not be drawn. If true set, active dot will be drawn which have the props calculated internally. Default: {"stroke": rx.color("accent", 10), "fill": rx.color("accent", 4)}',
    )

    active_dot: Var[ACTIVE_DOT_TYPE] = field(
        default=LiteralVar.create({
            "stroke": Color("accent", 2),
            "fill": Color("accent", 10),
        }),
        doc='The dot is shown when user enter an area chart and this chart has tooltip. If false set, no active dot will not be drawn. If true set, active dot will be drawn which have the props calculated internally. Default: {"stroke": rx.color("accent", 2), "fill": rx.color("accent", 10)}',
    )

    hide: Var[bool] = field(
        doc="Hides the line when true, useful when toggling visibility state via legend. Default: False"
    )

    connect_nulls: Var[bool] = field(
        doc="Whether to connect a graph line across null points."
    )

    unit: Var[str | int] = field(
        doc="The unit of data. This option will be used in tooltip."
    )

    points: Var[Sequence[dict[str, Any]]] = field(
        doc="The coordinates of all the points in the line, usually calculated internally."
    )

    stroke_dasharray: Var[str] = field(
        doc="The pattern of dashes and gaps used to paint the line."
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = ["LabelList", "ErrorBar"]


class Scatter(Recharts):
    """A Scatter component in Recharts."""

    tag = "Scatter"

    alias = "RechartsScatter"

    data: Var[Sequence[dict[str, Any]]] = field(
        doc="The source data, in which each element is an object."
    )

    name: Var[str] = field(
        doc="The name of the data. It is used to represent the scatter in legend."
    )

    legend_type: Var[LiteralLegendType] = field(
        doc="The type of icon in legend. If set to 'none', no legend item will be rendered. 'line' | 'plainline' | 'square' | 'rect'| 'circle' | 'cross' | 'diamond' | 'square' | 'star' | 'triangle' | 'wye' | 'none'. Default: \"circle\""
    )

    x_axis_id: Var[str | int] = field(
        doc="The id of x-axis which is corresponding to the data. Default: 0"
    )

    y_axis_id: Var[str | int] = field(
        doc="The id of y-axis which is corresponding to the data. Default: 0"
    )

    z_axis_id: Var[str | int] = field(
        doc="The id of z-axis which is corresponding to the data. Default: 0"
    )

    line: Var[bool] = field(
        doc="If false set, line will not be drawn. If true set, line will be drawn which have the props calculated internally. Default: False"
    )

    shape: Var[LiteralShape] = field(
        doc="If a string set, specified symbol will be used to show scatter item. 'circle' | 'cross' | 'diamond' | 'square' | 'star' | 'triangle' | 'wye'. Default: \"circle\""
    )

    line_type: Var[LiteralLineType] = field(
        doc="If 'joint' set, line will generated by just jointing all the points. If 'fitting' set, line will be generated by fitting algorithm. 'joint' | 'fitting'. Default: \"joint\""
    )

    fill: Var[str | Color] = field(
        default=LiteralVar.create(Color("accent", 9)),
        doc='The fill color of the scatter. Default: rx.color("accent", 9)',
    )

    # Valid children components.
    _valid_children: ClassVar[list[str]] = ["LabelList", "ErrorBar"]

    is_animation_active: Var[bool] = field(
        doc="If set false, animation of bar will be disabled. Default: True in CSR, False in SSR"
    )

    animation_begin: Var[int] = field(
        doc="Specifies when the animation should begin, the unit of this option is ms. Default: 0"
    )

    animation_duration: Var[int] = field(
        doc="Specifies the duration of animation, the unit of this option is ms. Default: 1500"
    )

    animation_easing: Var[LiteralAnimationEasing] = field(
        doc='The type of easing function. Default: "ease"'
    )

    on_click: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of click on the component in this group"
    )

    on_mouse_down: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mousedown on the component in this group"
    )

    on_mouse_up: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseup on the component in this group"
    )

    on_mouse_move: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mousemove on the component in this group"
    )

    on_mouse_over: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseover on the component in this group"
    )

    on_mouse_out: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseout on the component in this group"
    )

    on_mouse_enter: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseenter on the component in this group"
    )

    on_mouse_leave: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseleave on the component in this group"
    )


class Funnel(Recharts):
    """A Funnel component in Recharts."""

    tag = "Funnel"

    alias = "RechartsFunnel"

    data: Var[Sequence[dict[str, Any]]] = field(
        doc="The source data, in which each element is an object."
    )

    data_key: Var[str | int] = field(
        doc="The key or getter of a group of data which should be unique in a FunnelChart."
    )

    name_key: Var[str] = field(doc='The key of each sector\'s name. Default: "name"')

    legend_type: Var[LiteralLegendType] = field(
        doc="The type of icon in legend. If set to 'none', no legend item will be rendered. Default: \"line\""
    )

    is_animation_active: Var[bool] = field(
        doc="If set false, animation of line will be disabled. Default: True"
    )

    animation_begin: Var[int] = field(
        doc="Specifies when the animation should begin, the unit of this option is ms. Default: 0"
    )

    animation_duration: Var[int] = field(
        doc="Specifies the duration of animation, the unit of this option is ms. Default: 1500"
    )

    animation_easing: Var[LiteralAnimationEasing] = field(
        doc="The type of easing function. 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'linear'. Default \"ease\""
    )

    stroke: Var[str | Color] = field(
        default=LiteralVar.create(Color("gray", 3)),
        doc='Stroke color. Default: rx.color("gray", 3)',
    )

    trapezoids: Var[Sequence[dict[str, Any]]] = field(
        doc="The coordinates of all the trapezoids in the funnel, usually calculated internally."
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = ["LabelList", "Cell"]

    on_animation_start: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of animation start"
    )

    on_animation_end: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of animation end"
    )

    on_click: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of click on the component in this group"
    )

    on_mouse_down: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mousedown on the component in this group"
    )

    on_mouse_up: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseup on the component in this group"
    )

    on_mouse_move: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mousemove on the component in this group"
    )

    on_mouse_over: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseover on the component in this group"
    )

    on_mouse_out: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseout on the component in this group"
    )

    on_mouse_enter: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseenter on the component in this group"
    )

    on_mouse_leave: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseleave on the component in this group"
    )


class ErrorBar(Recharts):
    """An ErrorBar component in Recharts."""

    tag = "ErrorBar"

    alias = "RechartsErrorBar"

    direction: Var[LiteralDirection] = field(
        doc='Only used for ScatterChart with error bars in two directions. Only accepts a value of "x" or "y" and makes the error bars lie in that direction.'
    )

    data_key: Var[str | int] = field(
        doc="The key of a group of data which should be unique in an area chart."
    )

    width: Var[int] = field(doc="The width of the error bar ends. Default: 5")

    stroke: Var[str | Color] = field(
        default=LiteralVar.create(Color("gray", 8)),
        doc='The stroke color of error bar. Default: rx.color("gray", 8)',
    )

    stroke_width: Var[str | int | float] = field(
        doc="The stroke width of error bar. Default: 1.5"
    )


class Reference(Recharts):
    """A base class for reference components in Reference."""

    x_axis_id: Var[str | int] = field(
        doc="The id of x-axis which is corresponding to the data. Default: 0"
    )

    y_axis_id: Var[str | int] = field(
        doc="The id of y-axis which is corresponding to the data. Default: 0"
    )

    if_overflow: Var[LiteralIfOverflow] = field(
        doc="Defines how to draw the reference line if it falls partly outside the canvas. If set to 'discard', the reference line will not be drawn at all. If set to 'hidden', the reference line will be clipped to the canvas. If set to 'visible', the reference line will be drawn completely. If set to 'extendDomain', the domain of the overflown axis will be extended such that the reference line fits into the canvas. Default: \"discard\""
    )

    label: Var[str | int] = field(
        doc="If set a string or a number, default label will be drawn, and the option is content."
    )


class Segment(TypedDict):
    """A segment in a ReferenceLine or ReferenceArea."""

    x: str | int
    y: str | int


class ReferenceLine(Reference):
    """A ReferenceLine component in Recharts."""

    tag = "ReferenceLine"

    alias = "RechartsReferenceLine"

    x: Var[str | int] = field(
        doc="If set a string or a number, a vertical line perpendicular to the x-axis specified by xAxisId will be drawn. If the specified x-axis is a number axis, the type of x must be Number. If the specified x-axis is a category axis, the value of x must be one of the categorys, otherwise no line will be drawn."
    )

    y: Var[str | int] = field(
        doc="If set a string or a number, a horizontal line perpendicular to the y-axis specified by yAxisId will be drawn. If the specified y-axis is a number axis, the type of y must be Number. If the specified y-axis is a category axis, the value of y must be one of the categorys, otherwise no line will be drawn."
    )

    stroke: Var[str | Color] = field(doc="The color of the reference line.")

    stroke_width: Var[str | int | float] = field(
        doc="The width of the stroke. Default: 1"
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = ["Label"]

    segment: Var[Sequence[Segment]] = field(
        doc="Array of endpoints in { x, y } format. These endpoints would be used to draw the ReferenceLine."
    )


class ReferenceDot(Reference):
    """A ReferenceDot component in Recharts."""

    tag = "ReferenceDot"

    alias = "RechartsReferenceDot"

    x: Var[str | int] = field(
        doc="If set a string or a number, a vertical line perpendicular to the x-axis specified by xAxisId will be drawn. If the specified x-axis is a number axis, the type of x must be Number. If the specified x-axis is a category axis, the value of x must be one of the categorys, otherwise no line will be drawn."
    )

    y: Var[str | int] = field(
        doc="If set a string or a number, a horizontal line perpendicular to the y-axis specified by yAxisId will be drawn. If the specified y-axis is a number axis, the type of y must be Number. If the specified y-axis is a category axis, the value of y must be one of the categorys, otherwise no line will be drawn."
    )

    r: Var[int] = field(doc="The radius of dot.")

    fill: Var[str | Color] = field(doc="The color of the area fill.")

    stroke: Var[str | Color] = field(doc="The color of the line stroke.")

    # Valid children components
    _valid_children: ClassVar[list[str]] = ["Label"]

    on_click: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of click on the component in this chart"
    )

    on_mouse_down: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mousedown on the component in this chart"
    )

    on_mouse_up: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseup on the component in this chart"
    )

    on_mouse_over: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseover on the component in this chart"
    )

    on_mouse_out: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseout on the component in this chart"
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


class ReferenceArea(Recharts):
    """A ReferenceArea component in Recharts."""

    tag = "ReferenceArea"

    alias = "RechartsReferenceArea"

    stroke: Var[str | Color] = field(doc="Stroke color")

    fill: Var[str | Color] = field(doc="Fill color")

    fill_opacity: Var[float] = field(doc="The opacity of area.")

    x_axis_id: Var[str | int] = field(
        doc="The id of x-axis which is corresponding to the data."
    )

    y_axis_id: Var[str | int] = field(
        doc="The id of y-axis which is corresponding to the data."
    )

    x1: Var[str | int] = field(
        doc="A boundary value of the area. If the specified x-axis is a number axis, the type of x must be Number. If the specified x-axis is a category axis, the value of x must be one of the categorys. If one of x1 or x2 is invalidate, the area will cover along x-axis."
    )

    x2: Var[str | int] = field(
        doc="A boundary value of the area. If the specified x-axis is a number axis, the type of x must be Number. If the specified x-axis is a category axis, the value of x must be one of the categorys. If one of x1 or x2 is invalidate, the area will cover along x-axis."
    )

    y1: Var[str | int] = field(
        doc="A boundary value of the area. If the specified y-axis is a number axis, the type of y must be Number. If the specified y-axis is a category axis, the value of y must be one of the categorys. If one of y1 or y2 is invalidate, the area will cover along y-axis."
    )

    y2: Var[str | int] = field(
        doc="A boundary value of the area. If the specified y-axis is a number axis, the type of y must be Number. If the specified y-axis is a category axis, the value of y must be one of the categorys. If one of y1 or y2 is invalidate, the area will cover along y-axis."
    )

    if_overflow: Var[LiteralIfOverflow] = field(
        doc="Defines how to draw the reference line if it falls partly outside the canvas. If set to 'discard', the reference line will not be drawn at all. If set to 'hidden', the reference line will be clipped to the canvas. If set to 'visible', the reference line will be drawn completely. If set to 'extendDomain', the domain of the overflown axis will be extended such that the reference line fits into the canvas. Default: \"discard\""
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = ["Label"]


class Grid(Recharts):
    """A base class for grid components in Recharts."""

    x: Var[int] = field(doc="The x-coordinate of grid. Default: 0")

    y: Var[int] = field(doc="The y-coordinate of grid. Default: 0")

    width: Var[int] = field(doc="The width of grid. Default: 0")

    height: Var[int] = field(doc="The height of grid. Default: 0")


class CartesianGrid(Grid):
    """A CartesianGrid component in Recharts."""

    tag = "CartesianGrid"

    alias = "RechartsCartesianGrid"

    horizontal: Var[bool] = field(
        doc="The horizontal line configuration. Default: True"
    )

    vertical: Var[bool] = field(doc="The vertical line configuration. Default: True")

    vertical_points: Var[Sequence[str | int]] = field(
        doc="The x-coordinates in pixel values of all vertical lines. Default: []"
    )

    horizontal_points: Var[Sequence[str | int]] = field(
        doc="The x-coordinates in pixel values of all vertical lines. Default: []"
    )

    fill: Var[str | Color] = field(doc="The background of grid.")

    fill_opacity: Var[float] = field(
        doc="The opacity of the background used to fill the space between grid lines."
    )

    stroke_dasharray: Var[str] = field(
        doc="The pattern of dashes and gaps used to paint the lines of the grid."
    )

    stroke: Var[str | Color] = field(
        default=LiteralVar.create(Color("gray", 7)),
        doc='the stroke color of grid. Default: rx.color("gray", 7)',
    )


class CartesianAxis(Grid):
    """A CartesianAxis component in Recharts."""

    tag = "CartesianAxis"

    alias = "RechartsCartesianAxis"

    orientation: Var[LiteralOrientationTopBottomLeftRight] = field(
        doc="The orientation of axis 'top' | 'bottom' | 'left' | 'right'. Default: \"bottom\""
    )

    view_box: Var[dict[str, Any]] = field(
        doc='The box of viewing area. Default: {"x": 0, "y": 0, "width": 0, "height": 0}'
    )

    axis_line: Var[bool | dict] = field(
        doc="If set false, no axis line will be drawn. If set a object, the option is the configuration of axis line. Default: True"
    )

    tick: Var[bool | dict] = field(doc="If set false, no ticks will be drawn.")

    tick_line: Var[bool] = field(
        doc="If set false, no axis tick lines will be drawn. If set a object, the option is the configuration of tick lines. Default: True"
    )

    tick_size: Var[int] = field(doc="The length of tick line. Default: 6")

    interval: Var[LiteralInterval] = field(
        doc='If set 0, all the ticks will be shown. If set preserveStart", "preserveEnd" or "preserveStartEnd", the ticks which is to be shown or hidden will be calculated automatically. Default: "preserveEnd"'
    )

    label: Var[str | int] = field(
        doc="If set a string or a number, default label will be drawn, and the option is content."
    )

    mirror: Var[bool] = field(
        doc="If set true, flips ticks around the axis line, displaying the labels inside the chart instead of outside. Default: False"
    )

    tick_margin: Var[int] = field(doc="The margin between tick line and tick.")


area = Area.create
bar = Bar.create
line = Line.create
scatter = Scatter.create
x_axis = XAxis.create
y_axis = YAxis.create
z_axis = ZAxis.create
brush = Brush.create
cartesian_axis = CartesianAxis.create
cartesian_grid = CartesianGrid.create
reference_line = ReferenceLine.create
reference_dot = ReferenceDot.create
reference_area = ReferenceArea.create
error_bar = ErrorBar.create
funnel = Funnel.create
