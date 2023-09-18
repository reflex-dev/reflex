from typing import Any, Dict, List, Optional, Union

from reflex.components.component import Component
from reflex.style import Style
from reflex.vars import Var
from .recharts import Recharts


class Cartesian(Recharts):

    # The layout of bar in the chart, usually inherited from parent. 'horizontal' | 'vertical'
    layout: Var[str]

    # The key of a group of data which should be unique in an area chart.
    data_key: Var[str]

    # The id of x-axis which is corresponding to the data.
    x_axis_id: Var[str]

    # The id of y-axis which is corresponding to the data.
    y_axis_id: Var[str]

    # The type of icon in legend. If set to 'none', no legend item will be rendered. 'line' | 'plainline' | 'square' | 'rect'| 'circle' | 'cross' | 'diamond' | 'square' | 'star' | 'triangle' | 'wye' | 'none'optional
    legend_type: Var[str]


class Axis(Recharts):
    # The key of a group of data which should be unique in an area chart.
    data_key: Var[str]

    # If set true, the axis do not display in the chart.
    hide: Var[bool]

    # The orientation of axis 'top' | 'bottom'
    orientation: Var[str]

    # The type of axis 'number' | 'category'
    _type: Var[str]

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
    scale: Var[str]

    # The unit of data displayed in the axis. This option will be used to represent an index unit in a scatter chart.
    unit: Var[str]

    # The name of data displayed in the axis. This option will be used to represent an index in a scatter chart.
    name: Var[str]


class XAxis(Axis):

    tag = "XAxis"


class YAxis(Axis):

    tag = "YAxis"

    # The key of data displayed in the axis.
    data_key: Var[str]


class ZAxis(Cartesian):

    tag = "ZAxis"

    # The key of data displayed in the axis.
    data_key: Var[str]

    # The range of axis.
    range: Var[List[int]]

    # The unit of data displayed in the axis. This option will be used to represent an index unit in a scatter chart.
    unit: Var[str]

    # The name of data displayed in the axis. This option will be used to represent an index in a scatter chart.
    name: Var[str]

    # If 'auto' set, the scale function is decided by the type of chart, and the props type.
    scale: Var[str]


class Brush(Recharts):

    tag = "Brush"

    # The key of data displayed in the axis.
    data_key: Var[str]

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


class Area(Cartesian):

    tag = "Area"

    stroke: Var[str]

    fill: Var[str]


class Bar(Cartesian):

    tag = "Bar"

    stroke: Var[str]

    fill: Var[str]

class Line(Cartesian):

    tag = "Line"

    stroke: Var[str]

    stoke_width: Var[int]


class Scatter(Cartesian):

    tag = "Scatter"

    # The source data, in which each element is an object.
    data: Var[List[Dict[str, Any]]]

    # Specifies when the animation should begin, the unit of this option is ms.
    animation_begin: Var[int]

    # Specifies the duration of animation, the unit of this option is ms.
    animation_duration: Var[int]

    # The type of easing function. 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'linear'
    animation_easing: Var[str]


class Funnel(Cartesian):

    tag = "Funnel"

    # The source data, in which each element is an object.
    data: Var[List[Dict[str, Any]]]

    # Specifies when the animation should begin, the unit of this option is ms.
    animation_begin: Var[int]

    # Specifies the duration of animation, the unit of this option is ms.
    animation_duration: Var[int]

    # The type of easing function. 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'linear'
    animation_easing: Var[str]


class ErrorBar(Cartesian):

    tag = "ErrorBar"


class ReferenceLine(Recharts):

    tag = "ReferenceLine"


class ReferenceDot(Recharts):

    tag = "ReferenceDot"


class ReferenceArea(Recharts):

    tag = "ReferenceArea"


class CartesianGrid(Recharts):

    tag = "CartesianGrid"

    # The horizontal line configuration.
    horizontal: Var[Dict[str, Any]]

    # The vertical line configuration.
    vertical: Var[Dict[str, Any]]


class CartesianAxis(Cartesian):

    tag = "CartesianAxis"
