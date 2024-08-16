"""Cartesian charts in Recharts."""

from __future__ import annotations

from typing import Any, Dict, List, Union

from reflex.constants import EventTriggers
from reflex.constants.colors import Color
from reflex.event import EventHandler
from reflex.vars import Var

from .recharts import (
    LiteralAnimationEasing,
    LiteralAreaType,
    LiteralDirection,
    LiteralIfOverflow,
    LiteralInterval,
    LiteralLayout,
    LiteralLegendType,
    LiteralLineType,
    LiteralOrientationLeftRight,
    LiteralOrientationTopBottom,
    LiteralOrientationTopBottomLeftRight,
    LiteralPolarRadiusType,
    LiteralScale,
    LiteralShape,
    Recharts,
)


class Axis(Recharts):
    """A base class for axes in Recharts."""

    # The key of data displayed in the axis.
    data_key: Var[Union[str, int]]

    # If set true, the axis do not display in the chart.
    hide: Var[bool]

    # The width of axis which is usually calculated internally.
    width: Var[Union[str, int]]

    # The height of axis, which can be setted by user.
    height: Var[Union[str, int]]

    # The type of axis 'number' | 'category'
    type_: Var[LiteralPolarRadiusType]

    # Allow the ticks of XAxis to be decimals or not.
    allow_decimals: Var[bool]

    # When domain of the axis is specified and the type of the axis is 'number', if allowDataOverflow is set to be false, the domain will be adjusted when the minimum value of data is smaller than domain[0] or the maximum value of data is greater than domain[1] so that the axis displays all data values. If set to true, graphic elements (line, area, bars) will be clipped to conform to the specified domain.
    allow_data_overflow: Var[bool]

    # Allow the axis has duplicated categorys or not when the type of axis is "category".
    allow_duplicated_category: Var[bool]

    # If set false, no axis line will be drawn. If set a object, the option is the configuration of axis line.
    axis_line: Var[bool]

    # If set true, flips ticks around the axis line, displaying the labels inside the chart instead of outside.
    mirror: Var[bool]

    # Reverse the ticks or not.
    reversed: Var[bool]

    # The label of axis, which appears next to the axis.
    label: Var[Union[str, int, Dict[str, Any]]]

    # If 'auto' set, the scale function is decided by the type of chart, and the props type. 'auto' | 'linear' | 'pow' | 'sqrt' | 'log' | 'identity' | 'time' | 'band' | 'point' | 'ordinal' | 'quantile' | 'quantize' | 'utc' | 'sequential' | 'threshold' | Function
    scale: Var[LiteralScale]

    # The unit of data displayed in the axis. This option will be used to represent an index unit in a scatter chart.
    unit: Var[Union[str, int]]

    # The name of data displayed in the axis. This option will be used to represent an index in a scatter chart.
    name: Var[Union[str, int]]

    # Set the values of axis ticks manually.
    ticks: Var[List[Union[str, int]]]

    # If set false, no ticks will be drawn.
    tick: Var[bool]

    # The count of axis ticks.
    tick_count: Var[int]

    # If set false, no axis tick lines will be drawn.
    tick_line: Var[bool] = Var.create_safe(False)

    # The length of tick line.
    tick_size: Var[int]

    # The minimum gap between two adjacent labels
    min_tick_gap: Var[int]

    # The stroke color of axis
    stroke: Var[Union[str, Color]] = Var.create_safe(Color("gray", 9))

    # The text anchor of axis
    text_anchor: Var[str]  # 'start', 'middle', 'end'

    # The customized event handler of click on the ticks of this axis
    on_click: EventHandler[lambda: []]

    # The customized event handler of mousedown on the ticks of this axis
    on_mouse_down: EventHandler[lambda: []]

    # The customized event handler of mouseup on the ticks of this axis
    on_mouse_up: EventHandler[lambda: []]

    # The customized event handler of mousemove on the ticks of this axis
    on_mouse_move: EventHandler[lambda: []]

    # The customized event handler of mouseout on the ticks of this axis
    on_mouse_out: EventHandler[lambda: []]

    # The customized event handler of mouseenter on the ticks of this axis
    on_mouse_enter: EventHandler[lambda: []]

    # The customized event handler of mouseleave on the ticks of this axis
    on_mouse_leave: EventHandler[lambda: []]


class XAxis(Axis):
    """An XAxis component in Recharts."""

    tag = "XAxis"

    alias = "RechartsXAxis"

    # The orientation of axis 'top' | 'bottom'
    orientation: Var[LiteralOrientationTopBottom]

    # The id of x-axis which is corresponding to the data.
    x_axis_id: Var[Union[str, int]]

    # Ensures that all datapoints within a chart contribute to its domain calculation, even when they are hidden
    include_hidden: Var[bool] = Var.create_safe(False)

    # The range of the axis. Work best in conjuction with allow_data_overflow.
    domain: Var[List]


class YAxis(Axis):
    """A YAxis component in Recharts."""

    tag = "YAxis"

    alias = "RechartsYAxis"

    # The orientation of axis 'left' | 'right'
    orientation: Var[LiteralOrientationLeftRight]

    # The id of y-axis which is corresponding to the data.
    y_axis_id: Var[Union[str, int]]

    # The range of the axis. Work best in conjuction with allow_data_overflow.
    domain: Var[List]


class ZAxis(Recharts):
    """A ZAxis component in Recharts."""

    tag = "ZAxis"

    alias = "RechartszAxis"

    # The key of data displayed in the axis.
    data_key: Var[Union[str, int]]

    # The range of axis.
    range: Var[List[int]]

    # The unit of data displayed in the axis. This option will be used to represent an index unit in a scatter chart.
    unit: Var[Union[str, int]]

    # The name of data displayed in the axis. This option will be used to represent an index in a scatter chart.
    name: Var[Union[str, int]]

    # If 'auto' set, the scale function is decided by the type of chart, and the props type.
    scale: Var[LiteralScale]


class Brush(Recharts):
    """A Brush component in Recharts."""

    tag = "Brush"

    alias = "RechartsBrush"

    # Stroke color
    stroke: Var[Union[str, Color]] = Var.create_safe(Color("gray", 9))

    # The fill color of brush.
    fill: Var[Union[str, Color]] = Var.create_safe(Color("gray", 2))

    # The key of data displayed in the axis.
    data_key: Var[Union[str, int]]

    # The x-coordinate of brush.
    x: Var[int]

    # The y-coordinate of brush.
    y: Var[int]

    # The width of brush.
    width: Var[int]

    # The height of brush.
    height: Var[int]

    # The data domain of brush, [min, max].
    data: Var[List[Any]]

    # The width of each traveller.
    traveller_width: Var[int]

    # The data with gap of refreshing chart. If the option is not set, the chart will be refreshed every time
    gap: Var[int]

    # The default start index of brush. If the option is not set, the start index will be 0.
    start_index: Var[int]

    # The default end index of brush. If the option is not set, the end index will be 1.
    end_index: Var[int]

    # The fill color of brush
    fill: Var[Union[str, Color]]

    # The stroke color of brush
    stroke: Var[Union[str, Color]]

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            EventTriggers.ON_CHANGE: lambda: [],
        }


class Cartesian(Recharts):
    """A base class for cartesian charts in Recharts."""

    # The layout of bar in the chart, usually inherited from parent. 'horizontal' | 'vertical'
    layout: Var[LiteralLayout]

    # The key of a group of data which should be unique in an area chart.
    data_key: Var[Union[str, int]]

    # The id of x-axis which is corresponding to the data.
    x_axis_id: Var[Union[str, int]]

    # The id of y-axis which is corresponding to the data.
    y_axis_id: Var[Union[str, int]]

    # The type of icon in legend. If set to 'none', no legend item will be rendered. 'line' | 'plainline' | 'square' | 'rect'| 'circle' | 'cross' | 'diamond' | 'star' | 'triangle' | 'wye' | 'none'optional
    legend_type: Var[LiteralLegendType]

    # The customized event handler of click on the component in this group
    on_click: EventHandler[lambda: []]

    # The customized event handler of mousedown on the component in this group
    on_mouse_down: EventHandler[lambda: []]

    # The customized event handler of mouseup on the component in this group
    on_mouse_up: EventHandler[lambda: []]

    # The customized event handler of mousemove on the component in this group
    on_mouse_move: EventHandler[lambda: []]

    # The customized event handler of mouseover on the component in this group
    on_mouse_over: EventHandler[lambda: []]

    # The customized event handler of mouseout on the component in this group
    on_mouse_out: EventHandler[lambda: []]

    # The customized event handler of mouseenter on the component in this group
    on_mouse_enter: EventHandler[lambda: []]

    # The customized event handler of mouseleave on the component in this group
    on_mouse_leave: EventHandler[lambda: []]


class Area(Cartesian):
    """An Area component in Recharts."""

    tag = "Area"

    alias = "RechartsArea"

    # The color of the line stroke.
    stroke: Var[Union[str, Color]] = Var.create_safe(Color("accent", 9))

    # The width of the line stroke.
    stroke_width: Var[int] = Var.create_safe(1)

    # The color of the area fill.
    fill: Var[Union[str, Color]] = Var.create_safe(Color("accent", 5))

    # The interpolation type of area. And customized interpolation function can be set to type. 'basis' | 'basisClosed' | 'basisOpen' | 'bumpX' | 'bumpY' | 'bump' | 'linear' | 'linearClosed' | 'natural' | 'monotoneX' | 'monotoneY' | 'monotone' | 'step' | 'stepBefore' | 'stepAfter' |
    type_: Var[LiteralAreaType] = Var.create_safe("monotone", _var_is_string=True)

    # If false set, dots will not be drawn. If true set, dots will be drawn which have the props calculated internally.
    dot: Var[Union[bool, Dict[str, Any]]]

    # The dot is shown when user enter an area chart and this chart has tooltip. If false set, no active dot will not be drawn. If true set, active dot will be drawn which have the props calculated internally.
    active_dot: Var[Union[bool, Dict[str, Any]]] = Var.create_safe(
        {
            "stroke": Color("accent", 2),
            "fill": Color("accent", 10),
        }
    )

    # If set false, labels will not be drawn. If set true, labels will be drawn which have the props calculated internally.
    label: Var[bool]

    # The stack id of area, when two areas have the same value axis and same stack_id, then the two areas are stacked in order.
    stack_id: Var[Union[str, int]]

    # The unit of data. This option will be used in tooltip.
    unit: Var[Union[str, int]]

    # The name of data. This option will be used in tooltip and legend to represent a bar. If no value was set to this option, the value of dataKey will be used alternatively.
    name: Var[Union[str, int]]

    # Valid children components
    _valid_children: List[str] = ["LabelList"]


class Bar(Cartesian):
    """A Bar component in Recharts."""

    tag = "Bar"

    alias = "RechartsBar"

    # The color of the line stroke.
    stroke: Var[Union[str, Color]]

    # The width of the line stroke.
    stroke_width: Var[int]

    # The width of the line stroke.
    fill: Var[Union[str, Color]] = Var.create_safe(Color("accent", 9))
    # If false set, background of bars will not be drawn. If true set, background of bars will be drawn which have the props calculated internally.
    background: Var[bool]

    # If false set, labels will not be drawn. If true set, labels will be drawn which have the props calculated internally.
    label: Var[bool]

    # The stack id of bar, when two bars have the same value axis and same stack_id, then the two bars are stacked in order.
    stack_id: Var[str]

    # The unit of data. This option will be used in tooltip.
    unit: Var[Union[str, int]]

    # The minimal height of a bar in a horizontal BarChart, or the minimal width of a bar in a vertical BarChart. By default, 0 values are not shown. To visualize a 0 (or close to zero) point, set the minimal point size to a pixel value like 3. In stacked bar charts, minPointSize might not be respected for tightly packed values. So we strongly recommend not using this prop in stacked BarCharts.
    min_point_size: Var[int]

    # The name of data. This option will be used in tooltip and legend to represent a bar. If no value was set to this option, the value of dataKey will be used alternatively.
    name: Var[Union[str, int]]

    # Size of the bar (if one bar_size is set then a bar_size must be set for all bars)
    bar_size: Var[int]

    # Max size of the bar
    max_bar_size: Var[int]

    # The active bar is shown when a user enters a bar chart and this chart has tooltip. If set to false, no active bar will be drawn. If set to true, active bar will be drawn with the props calculated internally. If passed an object, active bar will be drawn, and the internally calculated props will be merged with the key value pairs of the passed object.
    # active_bar: Var[Union[bool, Dict[str, Any]]]

    # Valid children components
    _valid_children: List[str] = ["Cell", "LabelList", "ErrorBar"]

    # If set false, animation of bar will be disabled.
    is_animation_active: Var[bool]

    # Specifies when the animation should begin, the unit of this option is ms, default 0.
    animation_begin: Var[int]

    # Specifies the duration of animation, the unit of this option is ms, default 1500.
    animation_duration: Var[int]

    # The type of easing function, default 'ease'
    animation_easing: Var[LiteralAnimationEasing]

    # The customized event handler of animation start
    on_animation_start: EventHandler[lambda: []]

    # The customized event handler of animation end
    on_animation_end: EventHandler[lambda: []]


class Line(Cartesian):
    """A Line component in Recharts."""

    tag = "Line"

    alias = "RechartsLine"

    # The interpolation type of line. And customized interpolation function can be set to type. It's the same as type in Area.
    type_: Var[LiteralAreaType]

    # The color of the line stroke.
    stroke: Var[Union[str, Color]] = Var.create_safe(Color("accent", 9))

    # The width of the line stroke.
    stroke_width: Var[int]

    # The dot is shown when mouse enter a line chart and this chart has tooltip. If false set, no active dot will not be drawn. If true set, active dot will be drawn which have the props calculated internally.
    dot: Var[Union[bool, Dict[str, Any]]] = Var.create_safe(
        {
            "stroke": Color("accent", 10),
            "fill": Color("accent", 4),
        }
    )

    # The dot is shown when user enter an area chart and this chart has tooltip. If false set, no active dot will not be drawn. If true set, active dot will be drawn which have the props calculated internally.
    active_dot: Var[Union[bool, Dict[str, Any]]] = Var.create_safe(
        {
            "stroke": Color("accent", 2),
            "fill": Color("accent", 10),
        }
    )

    # If false set, labels will not be drawn. If true set, labels will be drawn which have the props calculated internally.
    label: Var[bool]

    # Hides the line when true, useful when toggling visibility state via legend.
    hide: Var[bool]

    # Whether to connect a graph line across null points.
    connect_nulls: Var[bool]

    # The unit of data. This option will be used in tooltip.
    unit: Var[Union[str, int]]

    # The name of data displayed in the axis. This option will be used to represent an index in a scatter chart.
    name: Var[Union[str, int]]

    # Valid children components
    _valid_children: List[str] = ["LabelList", "ErrorBar"]


class Scatter(Recharts):
    """A Scatter component in Recharts."""

    tag = "Scatter"

    alias = "RechartsScatter"

    # The source data, in which each element is an object.
    data: Var[List[Dict[str, Any]]]

    # The type of icon in legend. If set to 'none', no legend item will be rendered. 'line' | 'plainline' | 'square' | 'rect'| 'circle' | 'cross' | 'diamond' | 'square' | 'star' | 'triangle' | 'wye' | 'none'
    legend_type: Var[LiteralLegendType]

    # The id of x-axis which is corresponding to the data.
    x_axis_id: Var[Union[str, int]]

    # The id of y-axis which is corresponding to the data.
    y_axis_id: Var[Union[str, int]]

    # The id of z-axis which is corresponding to the data.
    z_axis_id: Var[str]

    # If false set, line will not be drawn. If true set, line will be drawn which have the props calculated internally.
    line: Var[bool]

    # If a string set, specified symbol will be used to show scatter item. 'circle' | 'cross' | 'diamond' | 'square' | 'star' | 'triangle' | 'wye'
    shape: Var[LiteralShape]

    # If 'joint' set, line will generated by just jointing all the points. If 'fitting' set, line will be generated by fitting algorithm. 'joint' | 'fitting'
    line_type: Var[LiteralLineType]

    # The fill
    fill: Var[Union[str, Color]] = Var.create_safe(Color("accent", 9))

    # the name
    name: Var[Union[str, int]]

    # Valid children components.
    _valid_children: List[str] = ["LabelList", "ErrorBar"]

    # If set false, animation of bar will be disabled.
    is_animation_active: Var[bool]

    # Specifies when the animation should begin, the unit of this option is ms, default 0.
    animation_begin: Var[int]

    # Specifies the duration of animation, the unit of this option is ms, default 1500.
    animation_duration: Var[int]

    # The type of easing function, default 'ease'
    animation_easing: Var[LiteralAnimationEasing]

    # The customized event handler of click on the component in this group
    on_click: EventHandler[lambda: []]

    # The customized event handler of mousedown on the component in this group
    on_mouse_down: EventHandler[lambda: []]

    # The customized event handler of mouseup on the component in this group
    on_mouse_up: EventHandler[lambda: []]

    # The customized event handler of mousemove on the component in this group
    on_mouse_move: EventHandler[lambda: []]

    # The customized event handler of mouseover on the component in this group
    on_mouse_over: EventHandler[lambda: []]

    # The customized event handler of mouseout on the component in this group
    on_mouse_out: EventHandler[lambda: []]

    # The customized event handler of mouseenter on the component in this group
    on_mouse_enter: EventHandler[lambda: []]

    # The customized event handler of mouseleave on the component in this group
    on_mouse_leave: EventHandler[lambda: []]


class Funnel(Recharts):
    """A Funnel component in Recharts."""

    tag = "Funnel"

    alias = "RechartsFunnel"

    # The source data, in which each element is an object.
    data: Var[List[Dict[str, Any]]]

    # The key of a group of data which should be unique in an area chart.
    data_key: Var[Union[str, int]]

    # The key or getter of a group of data which should be unique in a LineChart.
    name_key: Var[str]

    # The type of icon in legend. If set to 'none', no legend item will be rendered.
    legend_type: Var[LiteralLegendType]

    # If set false, animation of line will be disabled.
    is_animation_active: Var[bool]

    # Specifies when the animation should begin, the unit of this option is ms.
    animation_begin: Var[int]

    # Specifies the duration of animation, the unit of this option is ms.
    animation_duration: Var[int]

    # The type of easing function. 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'linear'
    animation_easing: Var[LiteralAnimationEasing]

    # stroke color
    stroke: Var[Union[str, Color]] = Var.create_safe(Color("gray", 3))

    # Valid children components
    _valid_children: List[str] = ["LabelList", "Cell"]

    # The customized event handler of animation start
    on_animation_start: EventHandler[lambda: []]

    # The customized event handler of animation end
    on_animation_end: EventHandler[lambda: []]

    # The customized event handler of click on the component in this group
    on_click: EventHandler[lambda: []]

    # The customized event handler of mousedown on the component in this group
    on_mouse_down: EventHandler[lambda: []]

    # The customized event handler of mouseup on the component in this group
    on_mouse_up: EventHandler[lambda: []]

    # The customized event handler of mousemove on the component in this group
    on_mouse_move: EventHandler[lambda: []]

    # The customized event handler of mouseover on the component in this group
    on_mouse_over: EventHandler[lambda: []]

    # The customized event handler of mouseout on the component in this group
    on_mouse_out: EventHandler[lambda: []]

    # The customized event handler of mouseenter on the component in this group
    on_mouse_enter: EventHandler[lambda: []]

    # The customized event handler of mouseleave on the component in this group
    on_mouse_leave: EventHandler[lambda: []]


class ErrorBar(Recharts):
    """An ErrorBar component in Recharts."""

    tag = "ErrorBar"

    alias = "RechartsErrorBar"

    # The direction of error bar. 'x' | 'y' | 'both'
    direction: Var[LiteralDirection]

    # The key of a group of data which should be unique in an area chart.
    data_key: Var[Union[str, int]]

    # The width of the error bar ends.
    width: Var[int]

    # The stroke color of error bar.
    stroke: Var[Union[str, Color]] = Var.create_safe(Color("gray", 8))

    # The stroke width of error bar.
    stroke_width: Var[int]


class Reference(Recharts):
    """A base class for reference components in Reference."""

    # The id of x-axis which is corresponding to the data.
    x_axis_id: Var[Union[str, int]]

    # The id of y-axis which is corresponding to the data.
    y_axis_id: Var[Union[str, int]]

    # Defines how to draw the reference line if it falls partly outside the canvas. If set to 'discard', the reference line will not be drawn at all. If set to 'hidden', the reference line will be clipped to the canvas. If set to 'visible', the reference line will be drawn completely. If set to 'extendDomain', the domain of the overflown axis will be extended such that the reference line fits into the canvas.
    if_overflow: Var[LiteralIfOverflow]

    # If set a string or a number, default label will be drawn, and the option is content.
    label: Var[Union[str, int]]

    # If set true, the line will be rendered in front of bars in BarChart, etc.
    is_front: Var[bool]


class ReferenceLine(Reference):
    """A ReferenceLine component in Recharts."""

    tag = "ReferenceLine"

    alias = "RechartsReferenceLine"

    # If set a string or a number, a vertical line perpendicular to the x-axis specified by xAxisId will be drawn. If the specified x-axis is a number axis, the type of x must be Number. If the specified x-axis is a category axis, the value of x must be one of the categorys, otherwise no line will be drawn.
    x: Var[Union[str, int]]

    # If set a string or a number, a horizontal line perpendicular to the y-axis specified by yAxisId will be drawn. If the specified y-axis is a number axis, the type of y must be Number. If the specified y-axis is a category axis, the value of y must be one of the categorys, otherwise no line will be drawn.
    y: Var[Union[str, int]]

    # The color of the reference line.
    stroke: Var[Union[str, Color]]

    # The width of the stroke.
    stroke_width: Var[Union[str, int]]

    # Valid children components
    _valid_children: List[str] = ["Label"]

    # Array of endpoints in { x, y } format. These endpoints would be used to draw the ReferenceLine.
    segment: List[Any] = []


class ReferenceDot(Reference):
    """A ReferenceDot component in Recharts."""

    tag = "ReferenceDot"

    alias = "RechartsReferenceDot"

    # If set a string or a number, a vertical line perpendicular to the x-axis specified by xAxisId will be drawn. If the specified x-axis is a number axis, the type of x must be Number. If the specified x-axis is a category axis, the value of x must be one of the categorys, otherwise no line will be drawn.
    x: Var[Union[str, int]]

    # If set a string or a number, a horizontal line perpendicular to the y-axis specified by yAxisId will be drawn. If the specified y-axis is a number axis, the type of y must be Number. If the specified y-axis is a category axis, the value of y must be one of the categorys, otherwise no line will be drawn.
    y: Var[Union[str, int]]

    # The radius of dot.
    r: Var[int]

    # The color of the area fill.
    fill: Var[Union[str, Color]]

    # The color of the line stroke.
    stroke: Var[Union[str, Color]]

    # Valid children components
    _valid_children: List[str] = ["Label"]

    # The customized event handler of click on the component in this chart
    on_click: EventHandler[lambda: []]

    # The customized event handler of mousedown on the component in this chart
    on_mouse_down: EventHandler[lambda: []]

    # The customized event handler of mouseup on the component in this chart
    on_mouse_up: EventHandler[lambda: []]

    # The customized event handler of mouseover on the component in this chart
    on_mouse_over: EventHandler[lambda: []]

    # The customized event handler of mouseout on the component in this chart
    on_mouse_out: EventHandler[lambda: []]

    # The customized event handler of mouseenter on the component in this chart
    on_mouse_enter: EventHandler[lambda: []]

    # The customized event handler of mousemove on the component in this chart
    on_mouse_move: EventHandler[lambda: []]

    # The customized event handler of mouseleave on the component in this chart
    on_mouse_leave: EventHandler[lambda: []]


class ReferenceArea(Recharts):
    """A ReferenceArea component in Recharts."""

    tag = "ReferenceArea"

    alias = "RechartsReferenceArea"

    # Stroke color
    stroke: Var[Union[str, Color]]

    # Fill color
    fill: Var[Union[str, Color]]

    # The opacity of area.
    fill_opacity: Var[float]

    # The id of x-axis which is corresponding to the data.
    x_axis_id: Var[Union[str, int]]

    # The id of y-axis which is corresponding to the data.
    y_axis_id: Var[Union[str, int]]

    # A boundary value of the area. If the specified x-axis is a number axis, the type of x must be Number. If the specified x-axis is a category axis, the value of x must be one of the categorys. If one of x1 or x2 is invalidate, the area will cover along x-axis.
    x1: Var[Union[str, int]]

    # A boundary value of the area. If the specified x-axis is a number axis, the type of x must be Number. If the specified x-axis is a category axis, the value of x must be one of the categorys. If one of x1 or x2 is invalidate, the area will cover along x-axis.
    x2: Var[Union[str, int]]

    # A boundary value of the area. If the specified y-axis is a number axis, the type of y must be Number. If the specified y-axis is a category axis, the value of y must be one of the categorys. If one of y1 or y2 is invalidate, the area will cover along y-axis.
    y1: Var[Union[str, int]]

    # A boundary value of the area. If the specified y-axis is a number axis, the type of y must be Number. If the specified y-axis is a category axis, the value of y must be one of the categorys. If one of y1 or y2 is invalidate, the area will cover along y-axis.
    y2: Var[Union[str, int]]

    # Defines how to draw the reference line if it falls partly outside the canvas. If set to 'discard', the reference line will not be drawn at all. If set to 'hidden', the reference line will be clipped to the canvas. If set to 'visible', the reference line will be drawn completely. If set to 'extendDomain', the domain of the overflown axis will be extended such that the reference line fits into the canvas.
    if_overflow: Var[LiteralIfOverflow]

    # If set true, the line will be rendered in front of bars in BarChart, etc.
    is_front: Var[bool]

    # Valid children components
    _valid_children: List[str] = ["Label"]


class Grid(Recharts):
    """A base class for grid components in Recharts."""

    # The x-coordinate of grid.
    x: Var[int]

    # The y-coordinate of grid.
    y: Var[int]

    # The width of grid.
    width: Var[int]

    # The height of grid.
    height: Var[int]


class CartesianGrid(Grid):
    """A CartesianGrid component in Recharts."""

    tag = "CartesianGrid"

    alias = "RechartsCartesianGrid"

    # The horizontal line configuration.
    horizontal: Var[bool]

    # The vertical line configuration.
    vertical: Var[bool]

    # The x-coordinates in pixel values of all vertical lines.
    vertical_points: Var[List[Union[str, int]]]

    # The x-coordinates in pixel values of all vertical lines.
    horizontal_points: Var[List[Union[str, int]]]

    # The background of grid.
    fill: Var[Union[str, Color]]

    # The opacity of the background used to fill the space between grid lines
    fill_opacity: Var[float]

    # The pattern of dashes and gaps used to paint the lines of the grid
    stroke_dasharray: Var[str]

    # the stroke color of grid
    stroke: Var[Union[str, Color]] = Var.create_safe(Color("gray", 7))


class CartesianAxis(Grid):
    """A CartesianAxis component in Recharts."""

    tag = "CartesianAxis"

    alias = "RechartsCartesianAxis"

    # The orientation of axis 'top' | 'bottom' | 'left' | 'right'
    orientation: Var[LiteralOrientationTopBottomLeftRight]

    # If set false, no axis line will be drawn. If set a object, the option is the configuration of axis line.
    axis_line: Var[bool]

    # If set false, no axis tick lines will be drawn. If set a object, the option is the configuration of tick lines.
    tick_line: Var[bool]

    # The length of tick line.
    tick_size: Var[int]

    # If set 0, all the ticks will be shown. If set preserveStart", "preserveEnd" or "preserveStartEnd", the ticks which is to be shown or hidden will be calculated automatically.
    interval: Var[LiteralInterval]

    # If set false, no ticks will be drawn.
    ticks: Var[bool]

    # If set a string or a number, default label will be drawn, and the option is content.
    label: Var[str]

    # If set true, flips ticks around the axis line, displaying the labels inside the chart instead of outside.
    mirror: Var[bool]

    # The margin between tick line and tick.
    tick_margin: Var[int]


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
