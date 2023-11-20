"""Cartesian charts in Recharts."""
from __future__ import annotations

from typing import Any, Dict, List, Union

from reflex.constants import EventTriggers
from reflex.vars import Var

from .recharts import (
    LiteralAnimationEasing,
    LiteralAreaType,
    LiteralDirection,
    LiteralIfOverflow,
    LiteralInterval,
    LiteralLayout,
    LiteralLineType,
    LiteralOrientationTopBottom,
    LiteralOrientationTopBottomLeftRight,
    LiteralPolarRadiusType,
    LiteralScale,
    LiteralShape,
    Recharts,
)


class Axis(Recharts):
    """A base class for axes in Recharts."""

    # The key of a group of data which should be unique in an area chart.
    data_key: Var[Union[str, int]]

    # If set true, the axis do not display in the chart.
    hide: Var[bool]

    # The orientation of axis 'top' | 'bottom'
    orientation: Var[LiteralOrientationTopBottom]

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

    # If set false, no axis tick lines will be drawn. If set a object, the option is the configuration of tick lines.
    tick_line: Var[bool]

    # If set true, flips ticks around the axis line, displaying the labels inside the chart instead of outside.
    mirror: Var[bool]

    # Reverse the ticks or not.
    reversed: Var[bool]

    # If 'auto' set, the scale function is decided by the type of chart, and the props type. 'auto' | 'linear' | 'pow' | 'sqrt' | 'log' | 'identity' | 'time' | 'band' | 'point' | 'ordinal' | 'quantile' | 'quantize' | 'utc' | 'sequential' | 'threshold' | Function
    scale: Var[LiteralScale]

    # The unit of data displayed in the axis. This option will be used to represent an index unit in a scatter chart.
    unit: Var[Union[str, int]]

    # The name of data displayed in the axis. This option will be used to represent an index in a scatter chart.
    name: Var[Union[str, int]]

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            EventTriggers.ON_CLICK: lambda: [],
            EventTriggers.ON_MOUSE_MOVE: lambda: [],
            EventTriggers.ON_MOUSE_OVER: lambda: [],
            EventTriggers.ON_MOUSE_OUT: lambda: [],
            EventTriggers.ON_MOUSE_ENTER: lambda: [],
            EventTriggers.ON_MOUSE_LEAVE: lambda: [],
        }


class XAxis(Axis):
    """An XAxis component in Recharts."""

    tag = "XAxis"

    alias = "RechartsXAxis"


class YAxis(Axis):
    """A YAxis component in Recharts."""

    tag = "YAxis"

    alias = "RechartsYAxis"

    # The key of data displayed in the axis.
    data_key: Var[Union[str, int]]


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
    stroke: Var[str]

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
    # legend_type: Var[LiteralLegendType]

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            EventTriggers.ON_CLICK: lambda: [],
            EventTriggers.ON_MOUSE_MOVE: lambda: [],
            EventTriggers.ON_MOUSE_OVER: lambda: [],
            EventTriggers.ON_MOUSE_OUT: lambda: [],
            EventTriggers.ON_MOUSE_ENTER: lambda: [],
            EventTriggers.ON_MOUSE_LEAVE: lambda: [],
        }


class Area(Cartesian):
    """An Area component in Recharts."""

    tag = "Area"

    alias = "RechartsArea"

    # The color of the line stroke.
    stroke: Var[str]

    # The width of the line stroke.
    stroke_width: Var[int]

    # The color of the area fill.
    fill: Var[str]

    # The interpolation type of area. And customized interpolation function can be set to type. 'basis' | 'basisClosed' | 'basisOpen' | 'bumpX' | 'bumpY' | 'bump' | 'linear' | 'linearClosed' | 'natural' | 'monotoneX' | 'monotoneY' | 'monotone' | 'step' | 'stepBefore' | 'stepAfter' |
    type_: Var[LiteralAreaType]

    # If false set, dots will not be drawn. If true set, dots will be drawn which have the props calculated internally.
    dot: Var[bool]

    # The dot is shown when user enter an area chart and this chart has tooltip. If false set, no active dot will not be drawn. If true set, active dot will be drawn which have the props calculated internally.
    active_dot: Var[bool]

    # If false set, labels will not be drawn. If true set, labels will be drawn which have the props calculated internally.
    label: Var[bool]

    # The stack id of area, when two areas have the same value axis and same stackId, then the two areas area stacked in order.
    stack_id: Var[str]

    # Valid children components
    _valid_children: List[str] = ["LabelList"]


class Bar(Cartesian):
    """A Bar component in Recharts."""

    tag = "Bar"

    alias = "RechartsBar"

    # The color of the line stroke.
    stroke: Var[str]

    # The width of the line stroke.
    stroke_width: Var[int]

    # The width of the line stroke.
    fill: Var[str]

    # If false set, background of bars will not be drawn. If true set, background of bars will be drawn which have the props calculated internally.
    background: Var[bool]

    # If false set, labels will not be drawn. If true set, labels will be drawn which have the props calculated internally.
    label: Var[bool]

    # The stack id of bar, when two areas have the same value axis and same stackId, then the two areas area stacked in order.
    stack_id: Var[str]

    # Size of the bar
    bar_size: Var[int]

    # Max size of the bar
    max_bar_size: Var[int]

    # Valid children components
    _valid_children: List[str] = ["Cell", "LabelList", "ErrorBar"]


class Line(Cartesian):
    """A Line component in Recharts."""

    tag = "Line"

    alias = "RechartsLine"

    # The interpolation type of line. And customized interpolation function can be set to type. It's the same as type in Area.
    type_: Var[LiteralAreaType]

    # The color of the line stroke.
    stroke: Var[str]

    # The width of the line stroke.
    stoke_width: Var[int]

    # The dot is shown when mouse enter a line chart and this chart has tooltip. If false set, no active dot will not be drawn. If true set, active dot will be drawn which have the props calculated internally.
    dot: Var[bool]

    # The dot is shown when user enter an area chart and this chart has tooltip. If false set, no active dot will not be drawn. If true set, active dot will be drawn which have the props calculated internally.
    active_dot: Var[bool]

    # If false set, labels will not be drawn. If true set, labels will be drawn which have the props calculated internally.
    label: Var[bool]

    # Hides the line when true, useful when toggling visibility state via legend.
    hide: Var[bool]

    # Whether to connect a graph line across null points.
    connect_nulls: Var[bool]

    # Valid children components
    _valid_children: List[str] = ["LabelList", "ErrorBar"]


class Scatter(Cartesian):
    """A Scatter component in Recharts."""

    tag = "Scatter"

    alias = "RechartsScatter"

    # The source data, in which each element is an object.
    data: Var[List[Dict[str, Any]]]

    # The id of z-axis which is corresponding to the data.
    z_axis_id: Var[str]

    # If false set, line will not be drawn. If true set, line will be drawn which have the props calculated internally.
    line: Var[bool]

    # If a string set, specified symbol will be used to show scatter item. 'circle' | 'cross' | 'diamond' | 'square' | 'star' | 'triangle' | 'wye'
    shape: Var[LiteralShape]

    # If 'joint' set, line will generated by just jointing all the points. If 'fitting' set, line will be generated by fitting algorithm. 'joint' | 'fitting'
    line_type: Var[LiteralLineType]

    # The fill
    fill: Var[str]

    # the name
    name: Var[Union[str, int]]

    # Valid children components.
    _valid_children: List[str] = ["LabelList", "ErrorBar"]


class Funnel(Cartesian):
    """A Funnel component in Recharts."""

    tag = "Funnel"

    alias = "RechartsFunnel"

    # The source data, in which each element is an object.
    data: Var[List[Dict[str, Any]]]

    # Specifies when the animation should begin, the unit of this option is ms.
    animation_begin: Var[int]

    # Specifies the duration of animation, the unit of this option is ms.
    animation_duration: Var[int]

    # The type of easing function. 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'linear'
    animation_easing: Var[LiteralAnimationEasing]

    # Valid children components
    _valid_children: List[str] = ["LabelList", "Cell"]


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
    stroke: Var[str]

    # The stroke width of error bar.
    stroke_width: Var[int]


class Reference(Recharts):
    """A base class for reference components in Reference."""

    # The id of x-axis which is corresponding to the data.
    x_axis_id: Var[Union[str, int]]

    # The id of y-axis which is corresponding to the data.
    y_axis_id: Var[Union[str, int]]

    # If set a string or a number, a vertical line perpendicular to the x-axis specified by xAxisId will be drawn. If the specified x-axis is a number axis, the type of x must be Number. If the specified x-axis is a category axis, the value of x must be one of the categorys, otherwise no line will be drawn.
    x: Var[str]

    # If set a string or a number, a horizontal line perpendicular to the y-axis specified by yAxisId will be drawn. If the specified y-axis is a number axis, the type of y must be Number. If the specified y-axis is a category axis, the value of y must be one of the categorys, otherwise no line will be drawn.
    y: Var[str]

    # Defines how to draw the reference line if it falls partly outside the canvas. If set to 'discard', the reference line will not be drawn at all. If set to 'hidden', the reference line will be clipped to the canvas. If set to 'visible', the reference line will be drawn completely. If set to 'extendDomain', the domain of the overflown axis will be extended such that the reference line fits into the canvas.
    if_overflow: Var[LiteralIfOverflow]

    # If set true, the line will be rendered in front of bars in BarChart, etc.
    is_front: Var[bool]


class ReferenceLine(Reference):
    """A ReferenceLine component in Recharts."""

    tag = "ReferenceLine"

    alias = "RechartsReferenceLine"

    # The width of the stroke.
    stroke_width: Var[int]

    # Valid children components
    _valid_children: List[str] = ["Label"]


class ReferenceDot(Reference):
    """A ReferenceDot component in Recharts."""

    tag = "ReferenceDot"

    alias = "RechartsReferenceDot"

    # Valid children components
    _valid_children: List[str] = ["Label"]

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            EventTriggers.ON_CLICK: lambda: [],
            EventTriggers.ON_MOUSE_MOVE: lambda: [],
            EventTriggers.ON_MOUSE_OVER: lambda: [],
            EventTriggers.ON_MOUSE_OUT: lambda: [],
            EventTriggers.ON_MOUSE_ENTER: lambda: [],
            EventTriggers.ON_MOUSE_LEAVE: lambda: [],
        }


class ReferenceArea(Recharts):
    """A ReferenceArea component in Recharts."""

    tag = "ReferenceArea"

    alias = "RechartsReferenceArea"

    # Stroke color
    stroke: Var[str]

    # Fill color
    fill: Var[str]

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
    horizontal: Var[Dict[str, Any]]

    # The vertical line configuration.
    vertical: Var[Dict[str, Any]]

    # The background of grid.
    fill: Var[str]

    # The opacity of the background used to fill the space between grid lines
    fill_opacity: Var[float]

    # The pattern of dashes and gaps used to paint the lines of the grid
    stroke_dasharray: Var[str]


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
