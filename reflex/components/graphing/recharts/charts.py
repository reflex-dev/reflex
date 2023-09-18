"""A module that defines the chart components in Recharts."""

from typing import Any, Dict, List, Union

from reflex.vars import Var

from .recharts import Recharts


class ChartBase(Recharts):
    """A component that wraps a victory lib."""

    # The source data, in which each element is an object.
    data: Var[List[Dict[str, Any]]]

    # If any two categorical charts(rx.line_chart, rx.area_chart, rx.bar_chart, rx.composed_chart) have the same sync_id, these two charts can sync the position tooltip, and the start_index, end_index of Brush.
    sync_id: Var[str]

    # When sync_id is provided, allows customisation of how the charts will synchronize tooltips and brushes. Using 'index' (default setting), other charts will reuse current datum's index within the data array. In cases where data does not have the same length, this might yield unexpected results. In that case use 'value' which will try to match other charts values, or a fully custom function which will receive tick, data as argument and should return an index. 'index' | 'value' | function
    sync_method: Var[str]

    # The width of chart container. String or Integer
    width: Var[Union[str, int]]

    # The height of chart container.
    height: Var[Union[str, int]]

    # The layout of area in the chart. 'horizontal' | 'vertical'
    layout: Var[str]

    # The sizes of whitespace around the chart.
    margin: Var[Dict[str, Any]]

    # The type of offset function used to generate the lower and upper values in the series array. The four types are built-in offsets in d3-shape. 'expand' | 'none' | 'wiggle' | 'silhouette'
    stack_offset: Var[str]


class AreaChart(ChartBase):
    """An Area chart component in Recharts."""

    tag = "AreaChart"

    # The base value of area. Number | 'dataMin' | 'dataMax' | 'auto'
    base_value: Var[Union[int, str]]


class BarChart(ChartBase):
    """A Bar chart component in Recharts."""

    tag = "BarChart"

    # The gap between two bar categories, which can be a percent value or a fixed value. Percentage | Number
    bar_category_gap: Var[str]

    # The gap between two bars in the same category, which can be a percent value or a fixed value. Percentage | Number
    bar_gap: Var[str]

    # The width of all the bars in the chart. Number
    bar_size: Var[int]

    # The maximum width of all the bars in a horizontal BarChart, or maximum height in a vertical BarChart.
    bar_size_max: Var[int]

    # If false set, stacked items will be rendered left to right. If true set, stacked items will be rendered right to left. (Render direction affects SVG layering, not x position.)
    reverse_stack_order: Var[bool]


class LineChart(ChartBase):
    """A Line chart component in Recharts."""

    tag = "LineChart"


class ComposedChart(ChartBase):
    """A Composed chart component in Recharts."""

    tag = "ComposedChart"

    # The base value of area. Number | 'dataMin' | 'dataMax' | 'auto'
    base_value: Var[Union[int, str]]

    # The gap between two bar categories, which can be a percent value or a fixed value. Percentage | Number
    bar_category_gap: Var[str]

    # The gap between two bars in the same category, which can be a percent value or a fixed value. Percentage | Number
    bar_gap: Var[str]

    # The width of all the bars in the chart. Number
    bar_size: Var[int]

    # If false set, stacked items will be rendered left to right. If true set, stacked items will be rendered right to left. (Render direction affects SVG layering, not x position.)
    reverse_stack_order: Var[bool]


class PieChart(ChartBase):
    """A Pie chart component in Recharts."""

    tag = "PieChart"


class RadarChart(ChartBase):
    """A Radar chart component in Recharts."""

    tag = "RadarChart"

    # The The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of width. Number | Percentage
    cx: Var[Union[int, str]]

    # The The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of height. Number | Percentage
    cy: Var[Union[int, str]]

    # The angle of first radial direction line.
    start_angle: Var[int]

    # The angle of last point in the circle which should be startAngle - 360 or startAngle + 360. We'll calculate the direction of chart by 'startAngle' and 'endAngle'.
    end_angle: Var[int]

    # The inner radius of first circle grid. If set a percentage, the final value is obtained by multiplying the percentage of maxRadius which is calculated by the width, height, cx, cy. Number | Percentage
    inner_radius: Var[Union[int, str]]

    # The outer radius of last circle grid. If set a percentage, the final value is obtained by multiplying the percentage of maxRadius which is calculated by the width, height, cx, cy. Number | Percentage
    outer_radius: Var[Union[int, str]]


class RadialBarChart(ChartBase):
    """A RadialBar chart component in Recharts."""

    tag = "RadialBarChart"

    # The The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of width. Number | Percentage
    cx: Var[Union[int, str]]

    # The The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of height. Number | Percentage
    cy: Var[Union[int, str]]

    # The angle of first radial direction line.
    start_angle: Var[int]

    # The angle of last point in the circle which should be startAngle - 360 or startAngle + 360. We'll calculate the direction of chart by 'startAngle' and 'endAngle'.
    end_angle: Var[int]

    # The inner radius of first circle grid. If set a percentage, the final value is obtained by multiplying the percentage of maxRadius which is calculated by the width, height, cx, cy. Number | Percentage
    inner_radius: Var[Union[int, str]]

    # The outer radius of last circle grid. If set a percentage, the final value is obtained by multiplying the percentage of maxRadius which is calculated by the width, height, cx, cy. Number | Percentage
    outer_radius: Var[Union[int, str]]

    # The gap between two bar categories, which can be a percent value or a fixed value. Percentage | Number
    bar_category_gap: Var[str]

    # The gap between two bars in the same category, which can be a percent value or a fixed value. Percentage | Number
    bar_gap: Var[str]


class ScatterChart(ChartBase):
    """A Scatter chart component in Recharts."""

    tag = "ScatterChart"


class FunnelChart(ChartBase):
    """A Funnel chart component in Recharts."""

    tag = "FunnelChart"

    # The layout of bars in the chart. centeric
    layout: Var[str]


class Treemap(ChartBase):
    """A Treemap chart component in Recharts."""

    tag = "Treemap"

    # The key of a group of data which should be unique in a treemap. String | Number | Function
    data_key: Var[Union[str, int]]

    # The treemap will try to keep every single rectangle's aspect ratio near the aspectRatio given. Number
    aspect_ratio: Var[int]

    # If set false, animation of area will be disabled.
    is_animation_active: Var[bool]

    # Specifies when the animation should begin, the unit of this option is ms.
    animation_begin: Var[int]

    # Specifies the duration of animation, the unit of this option is ms.
    animation_duration: Var[int]

    # The type of easing function. 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'linear'
    animation_easing: Var[str]
