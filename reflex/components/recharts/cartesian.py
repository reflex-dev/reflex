"""Cartesian charts in Recharts."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

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
    data_key: Optional[Var[Union[str, int]]] = None

    # If set true, the axis do not display in the chart.
    hide: Optional[Var[bool]] = None

    # The orientation of axis 'top' | 'bottom'
    orientation: Optional[Var[LiteralOrientationTopBottom]] = None

    # The type of axis 'number' | 'category'
    type_: Optional[Var[LiteralPolarRadiusType]] = None

    # Allow the ticks of XAxis to be decimals or not.
    allow_decimals: Optional[Var[bool]] = None

    # When domain of the axis is specified and the type of the axis is 'number', if allowDataOverflow is set to be false, the domain will be adjusted when the minimum value of data is smaller than domain[0] or the maximum value of data is greater than domain[1] so that the axis displays all data values. If set to true, graphic elements (line, area, bars) will be clipped to conform to the specified domain.
    allow_data_overflow: Optional[Var[bool]] = None

    # Allow the axis has duplicated categorys or not when the type of axis is "category".
    allow_duplicated_category: Optional[Var[bool]] = None

    # If set false, no axis line will be drawn. If set a object, the option is the configuration of axis line.
    axis_line: Optional[Var[bool]] = None

    # If set false, no axis tick lines will be drawn. If set a object, the option is the configuration of tick lines.
    tick_line: Optional[Var[bool]] = None

    # If set true, flips ticks around the axis line, displaying the labels inside the chart instead of outside.
    mirror: Optional[Var[bool]] = None

    # Reverse the ticks or not.
    reversed: Optional[Var[bool]] = None

    # If 'auto' set, the scale function is decided by the type of chart, and the props type. 'auto' | 'linear' | 'pow' | 'sqrt' | 'log' | 'identity' | 'time' | 'band' | 'point' | 'ordinal' | 'quantile' | 'quantize' | 'utc' | 'sequential' | 'threshold' | Function
    scale: Optional[Var[LiteralScale]] = None

    # The unit of data displayed in the axis. This option will be used to represent an index unit in a scatter chart.
    unit: Optional[Var[Union[str, int]]] = None

    # The name of data displayed in the axis. This option will be used to represent an index in a scatter chart.
    name: Optional[Var[Union[str, int]]] = None

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

    tag: str = "XAxis"

    alias = "RechartsXAxis"


class YAxis(Axis):
    """A YAxis component in Recharts."""

    tag: str = "YAxis"

    alias = "RechartsYAxis"

    # The key of data displayed in the axis.
    data_key: Optional[Var[Union[str, int]]] = None


class ZAxis(Recharts):
    """A ZAxis component in Recharts."""

    tag: str = "ZAxis"

    alias = "RechartszAxis"

    # The key of data displayed in the axis.
    data_key: Optional[Var[Union[str, int]]] = None

    # The range of axis.
    range: Optional[Var[List[int]]] = None

    # The unit of data displayed in the axis. This option will be used to represent an index unit in a scatter chart.
    unit: Optional[Var[Union[str, int]]] = None

    # The name of data displayed in the axis. This option will be used to represent an index in a scatter chart.
    name: Optional[Var[Union[str, int]]] = None

    # If 'auto' set, the scale function is decided by the type of chart, and the props type.
    scale: Optional[Var[LiteralScale]] = None


class Brush(Recharts):
    """A Brush component in Recharts."""

    tag: str = "Brush"

    alias = "RechartsBrush"

    # Stroke color
    stroke: Optional[Var[str]] = None

    # The key of data displayed in the axis.
    data_key: Optional[Var[Union[str, int]]] = None

    # The x-coordinate of brush.
    x: Optional[Var[int]] = None

    # The y-coordinate of brush.
    y: Optional[Var[int]] = None

    # The width of brush.
    width: Optional[Var[int]] = None

    # The height of brush.
    height: Optional[Var[int]] = None

    # The data domain of brush, [min, max].
    data: Optional[Var[List[Any]]] = None

    # The width of each traveller.
    traveller_width: Optional[Var[int]] = None

    # The data with gap of refreshing chart. If the option is not set, the chart will be refreshed every time
    gap: Optional[Var[int]] = None

    # The default start index of brush. If the option is not set, the start index will be 0.
    start_index: Optional[Var[int]] = None

    # The default end index of brush. If the option is not set, the end index will be 1.
    end_index: Optional[Var[int]] = None

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
    layout: Optional[Var[LiteralLayout]] = None

    # The key of a group of data which should be unique in an area chart.
    data_key: Optional[Var[Union[str, int]]] = None

    # The id of x-axis which is corresponding to the data.
    x_axis_id: Optional[Var[Union[str, int]]] = None

    # The id of y-axis which is corresponding to the data.
    y_axis_id: Optional[Var[Union[str, int]]] = None

    # The type of icon in legend. If set to 'none', no legend item will be rendered. 'line' | 'plainline' | 'square' | 'rect'| 'circle' | 'cross' | 'diamond' | 'star' | 'triangle' | 'wye' | 'none'optional
    # legend_type: Optional[Var[LiteralLegendType]] = None

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

    tag: str = "Area"

    alias = "RechartsArea"

    # The color of the line stroke.
    stroke: Optional[Var[str]] = None

    # The width of the line stroke.
    stroke_width: Optional[Var[int]] = None

    # The color of the area fill.
    fill: Optional[Var[str]] = None

    # The interpolation type of area. And customized interpolation function can be set to type. 'basis' | 'basisClosed' | 'basisOpen' | 'bumpX' | 'bumpY' | 'bump' | 'linear' | 'linearClosed' | 'natural' | 'monotoneX' | 'monotoneY' | 'monotone' | 'step' | 'stepBefore' | 'stepAfter' |
    type_: Optional[Var[LiteralAreaType]] = None

    # If false set, dots will not be drawn. If true set, dots will be drawn which have the props calculated internally.
    dot: Optional[Var[bool]] = None

    # The dot is shown when user enter an area chart and this chart has tooltip. If false set, no active dot will not be drawn. If true set, active dot will be drawn which have the props calculated internally.
    active_dot: Optional[Var[bool]] = None

    # If false set, labels will not be drawn. If true set, labels will be drawn which have the props calculated internally.
    label: Optional[Var[bool]] = None

    # The stack id of area, when two areas have the same value axis and same stackId, then the two areas area stacked in order.
    stack_id: Optional[Var[str]] = None

    # Valid children components
    _valid_children: List[str] = ["LabelList"]


class Bar(Cartesian):
    """A Bar component in Recharts."""

    tag: str = "Bar"

    alias = "RechartsBar"

    # The color of the line stroke.
    stroke: Optional[Var[str]] = None

    # The width of the line stroke.
    stroke_width: Optional[Var[int]] = None

    # The width of the line stroke.
    fill: Optional[Var[str]] = None

    # If false set, background of bars will not be drawn. If true set, background of bars will be drawn which have the props calculated internally.
    background: Optional[Var[bool]] = None

    # If false set, labels will not be drawn. If true set, labels will be drawn which have the props calculated internally.
    label: Optional[Var[bool]] = None

    # The stack id of bar, when two areas have the same value axis and same stackId, then the two areas area stacked in order.
    stack_id: Optional[Var[str]] = None

    # Size of the bar
    bar_size: Optional[Var[int]] = None

    # Max size of the bar
    max_bar_size: Optional[Var[int]] = None

    # Valid children components
    _valid_children: List[str] = ["Cell", "LabelList", "ErrorBar"]


class Line(Cartesian):
    """A Line component in Recharts."""

    tag: str = "Line"

    alias = "RechartsLine"

    # The interpolation type of line. And customized interpolation function can be set to type. It's the same as type in Area.
    type_: Optional[Var[LiteralAreaType]] = None

    # The color of the line stroke.
    stroke: Optional[Var[str]] = None

    # The width of the line stroke.
    stoke_width: Optional[Var[int]] = None

    # The dot is shown when mouse enter a line chart and this chart has tooltip. If false set, no active dot will not be drawn. If true set, active dot will be drawn which have the props calculated internally.
    dot: Optional[Var[bool]] = None

    # The dot is shown when user enter an area chart and this chart has tooltip. If false set, no active dot will not be drawn. If true set, active dot will be drawn which have the props calculated internally.
    active_dot: Optional[Var[bool]] = None

    # If false set, labels will not be drawn. If true set, labels will be drawn which have the props calculated internally.
    label: Optional[Var[bool]] = None

    # Hides the line when true, useful when toggling visibility state via legend.
    hide: Optional[Var[bool]] = None

    # Whether to connect a graph line across null points.
    connect_nulls: Optional[Var[bool]] = None

    # Valid children components
    _valid_children: List[str] = ["LabelList", "ErrorBar"]


class Scatter(Cartesian):
    """A Scatter component in Recharts."""

    tag: str = "Scatter"

    alias = "RechartsScatter"

    # The source data, in which each element is an object.
    data: Optional[Var[List[Dict[str, Any]]]] = None

    # The id of z-axis which is corresponding to the data.
    z_axis_id: Optional[Var[str]] = None

    # If false set, line will not be drawn. If true set, line will be drawn which have the props calculated internally.
    line: Optional[Var[bool]] = None

    # If a string set, specified symbol will be used to show scatter item. 'circle' | 'cross' | 'diamond' | 'square' | 'star' | 'triangle' | 'wye'
    shape: Optional[Var[LiteralShape]] = None

    # If 'joint' set, line will generated by just jointing all the points. If 'fitting' set, line will be generated by fitting algorithm. 'joint' | 'fitting'
    line_type: Optional[Var[LiteralLineType]] = None

    # The fill
    fill: Optional[Var[str]] = None

    # the name
    name: Optional[Var[Union[str, int]]] = None

    # Valid children components.
    _valid_children: List[str] = ["LabelList", "ErrorBar"]


class Funnel(Cartesian):
    """A Funnel component in Recharts."""

    tag: str = "Funnel"

    alias = "RechartsFunnel"

    # The source data, in which each element is an object.
    data: Optional[Var[List[Dict[str, Any]]]] = None

    # Specifies when the animation should begin, the unit of this option is ms.
    animation_begin: Optional[Var[int]] = None

    # Specifies the duration of animation, the unit of this option is ms.
    animation_duration: Optional[Var[int]] = None

    # The type of easing function. 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'linear'
    animation_easing: Optional[Var[LiteralAnimationEasing]] = None

    # Valid children components
    _valid_children: List[str] = ["LabelList", "Cell"]


class ErrorBar(Recharts):
    """An ErrorBar component in Recharts."""

    tag: str = "ErrorBar"

    alias = "RechartsErrorBar"

    # The direction of error bar. 'x' | 'y' | 'both'
    direction: Optional[Var[LiteralDirection]] = None

    # The key of a group of data which should be unique in an area chart.
    data_key: Optional[Var[Union[str, int]]] = None

    # The width of the error bar ends.
    width: Optional[Var[int]] = None

    # The stroke color of error bar.
    stroke: Optional[Var[str]] = None

    # The stroke width of error bar.
    stroke_width: Optional[Var[int]] = None


class Reference(Recharts):
    """A base class for reference components in Reference."""

    # The id of x-axis which is corresponding to the data.
    x_axis_id: Optional[Var[Union[str, int]]] = None

    # The id of y-axis which is corresponding to the data.
    y_axis_id: Optional[Var[Union[str, int]]] = None

    # If set a string or a number, a vertical line perpendicular to the x-axis specified by xAxisId will be drawn. If the specified x-axis is a number axis, the type of x must be Number. If the specified x-axis is a category axis, the value of x must be one of the categorys, otherwise no line will be drawn.
    x: Optional[Var[str]] = None

    # If set a string or a number, a horizontal line perpendicular to the y-axis specified by yAxisId will be drawn. If the specified y-axis is a number axis, the type of y must be Number. If the specified y-axis is a category axis, the value of y must be one of the categorys, otherwise no line will be drawn.
    y: Optional[Var[str]] = None

    # Defines how to draw the reference line if it falls partly outside the canvas. If set to 'discard', the reference line will not be drawn at all. If set to 'hidden', the reference line will be clipped to the canvas. If set to 'visible', the reference line will be drawn completely. If set to 'extendDomain', the domain of the overflown axis will be extended such that the reference line fits into the canvas.
    if_overflow: Optional[Var[LiteralIfOverflow]] = None

    # If set true, the line will be rendered in front of bars in BarChart, etc.
    is_front: Optional[Var[bool]] = None


class ReferenceLine(Reference):
    """A ReferenceLine component in Recharts."""

    tag: str = "ReferenceLine"

    alias = "RechartsReferenceLine"

    # The width of the stroke.
    stroke_width: Optional[Var[int]] = None

    # Valid children components
    _valid_children: List[str] = ["Label"]


class ReferenceDot(Reference):
    """A ReferenceDot component in Recharts."""

    tag: str = "ReferenceDot"

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

    tag: str = "ReferenceArea"

    alias = "RechartsReferenceArea"

    # Stroke color
    stroke: Optional[Var[str]] = None

    # Fill color
    fill: Optional[Var[str]] = None

    # The opacity of area.
    fill_opacity: Optional[Var[float]] = None

    # The id of x-axis which is corresponding to the data.
    x_axis_id: Optional[Var[Union[str, int]]] = None

    # The id of y-axis which is corresponding to the data.
    y_axis_id: Optional[Var[Union[str, int]]] = None

    # A boundary value of the area. If the specified x-axis is a number axis, the type of x must be Number. If the specified x-axis is a category axis, the value of x must be one of the categorys. If one of x1 or x2 is invalidate, the area will cover along x-axis.
    x1: Optional[Var[Union[str, int]]] = None

    # A boundary value of the area. If the specified x-axis is a number axis, the type of x must be Number. If the specified x-axis is a category axis, the value of x must be one of the categorys. If one of x1 or x2 is invalidate, the area will cover along x-axis.
    x2: Optional[Var[Union[str, int]]] = None

    # A boundary value of the area. If the specified y-axis is a number axis, the type of y must be Number. If the specified y-axis is a category axis, the value of y must be one of the categorys. If one of y1 or y2 is invalidate, the area will cover along y-axis.
    y1: Optional[Var[Union[str, int]]] = None

    # A boundary value of the area. If the specified y-axis is a number axis, the type of y must be Number. If the specified y-axis is a category axis, the value of y must be one of the categorys. If one of y1 or y2 is invalidate, the area will cover along y-axis.
    y2: Optional[Var[Union[str, int]]] = None

    # Defines how to draw the reference line if it falls partly outside the canvas. If set to 'discard', the reference line will not be drawn at all. If set to 'hidden', the reference line will be clipped to the canvas. If set to 'visible', the reference line will be drawn completely. If set to 'extendDomain', the domain of the overflown axis will be extended such that the reference line fits into the canvas.
    if_overflow: Optional[Var[LiteralIfOverflow]] = None

    # If set true, the line will be rendered in front of bars in BarChart, etc.
    is_front: Optional[Var[bool]] = None

    # Valid children components
    _valid_children: List[str] = ["Label"]


class Grid(Recharts):
    """A base class for grid components in Recharts."""

    # The x-coordinate of grid.
    x: Optional[Var[int]] = None

    # The y-coordinate of grid.
    y: Optional[Var[int]] = None

    # The width of grid.
    width: Optional[Var[int]] = None

    # The height of grid.
    height: Optional[Var[int]] = None


class CartesianGrid(Grid):
    """A CartesianGrid component in Recharts."""

    tag: str = "CartesianGrid"

    alias = "RechartsCartesianGrid"

    # The horizontal line configuration.
    horizontal: Optional[Var[Dict[str, Any]]] = None

    # The vertical line configuration.
    vertical: Optional[Var[Dict[str, Any]]] = None

    # The background of grid.
    fill: Optional[Var[str]] = None

    # The opacity of the background used to fill the space between grid lines
    fill_opacity: Optional[Var[float]] = None

    # The pattern of dashes and gaps used to paint the lines of the grid
    stroke_dasharray: Optional[Var[str]] = None


class CartesianAxis(Grid):
    """A CartesianAxis component in Recharts."""

    tag: str = "CartesianAxis"

    alias = "RechartsCartesianAxis"

    # The orientation of axis 'top' | 'bottom' | 'left' | 'right'
    orientation: Optional[Var[LiteralOrientationTopBottomLeftRight]] = None

    # If set false, no axis line will be drawn. If set a object, the option is the configuration of axis line.
    axis_line: Optional[Var[bool]] = None

    # If set false, no axis tick lines will be drawn. If set a object, the option is the configuration of tick lines.
    tick_line: Optional[Var[bool]] = None

    # The length of tick line.
    tick_size: Optional[Var[int]] = None

    # If set 0, all the ticks will be shown. If set preserveStart", "preserveEnd" or "preserveStartEnd", the ticks which is to be shown or hidden will be calculated automatically.
    interval: Optional[Var[LiteralInterval]] = None

    # If set false, no ticks will be drawn.
    ticks: Optional[Var[bool]] = None

    # If set a string or a number, default label will be drawn, and the option is content.
    label: Optional[Var[str]] = None

    # If set true, flips ticks around the axis line, displaying the labels inside the chart instead of outside.
    mirror: Optional[Var[bool]] = None

    # The margin between tick line and tick.
    tick_margin: Optional[Var[int]] = None
