"""A module that defines the chart components in Recharts."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from reflex.components.component import Component
from reflex.components.recharts.general import ResponsiveContainer
from reflex.constants import EventTriggers
from reflex.vars import Var

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

    # The source data, in which each element is an object.
    data: Optional[Var[List[Dict[str, Any]]]] = None

    # If any two categorical charts(rx.line_chart, rx.area_chart, rx.bar_chart, rx.composed_chart) have the same sync_id, these two charts can sync the position GraphingTooltip, and the start_index, end_index of Brush.
    sync_id: Optional[Var[str]] = None

    # When sync_id is provided, allows customisation of how the charts will synchronize GraphingTooltips and brushes. Using 'index' (default setting), other charts will reuse current datum's index within the data array. In cases where data does not have the same length, this might yield unexpected results. In that case use 'value' which will try to match other charts values, or a fully custom function which will receive tick, data as argument and should return an index. 'index' | 'value' | function
    sync_method: Optional[Var[LiteralSyncMethod]] = None

    # The width of chart container. String or Integer
    width: Var[Union[str, int]] = "100%"  # type: ignore

    # The height of chart container.
    height: Var[Union[str, int]] = "100%"  # type: ignore

    # The layout of area in the chart. 'horizontal' | 'vertical'
    layout: Optional[Var[LiteralLayout]] = None

    # The sizes of whitespace around the chart.
    margin: Optional[Var[Dict[str, Any]]] = None

    # The type of offset function used to generate the lower and upper values in the series array. The four types are built-in offsets in d3-shape. 'expand' | 'none' | 'wiggle' | 'silhouette'
    stack_offset: Optional[Var[LiteralStackOffset]] = None

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            EventTriggers.ON_CLICK: lambda: [],
            EventTriggers.ON_MOUSE_ENTER: lambda: [],
            EventTriggers.ON_MOUSE_MOVE: lambda: [],
            EventTriggers.ON_MOUSE_LEAVE: lambda: [],
        }

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
        raise ValueError(
            f"Chart {name} must be specified as int pixels or percentage, not {value!r}. "
            "CSS unit dimensions are allowed on parent container."
        )

    @classmethod
    def create(cls, *children, **props) -> Component:
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

        dim_props = dict(
            width=width or "100%",
            height=height or "100%",
        )
        # Provide min dimensions so the graph always appears, even if the outer container is zero-size.
        if width is None:
            dim_props["min_width"] = 200
        if height is None:
            dim_props["min_height"] = 100

        return ResponsiveContainer.create(
            super().create(*children, **props),
            **dim_props,  # type: ignore
        )


class AreaChart(ChartBase):
    """An Area chart component in Recharts."""

    tag: str = "AreaChart"

    alias = "RechartsAreaChart"

    # The base value of area. Number | 'dataMin' | 'dataMax' | 'auto'
    base_value: Optional[Var[Union[int, LiteralComposedChartBaseValue]]] = None

    # The type of offset function used to generate the lower and upper values in the series array. The four types are built-in offsets in d3-shape.
    stack_offset: Optional[Var[LiteralStackOffset]] = None

    # Valid children components
    _valid_children: List[str] = [
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
    ]


class BarChart(ChartBase):
    """A Bar chart component in Recharts."""

    tag: str = "BarChart"

    alias = "RechartsBarChart"

    # The gap between two bar categories, which can be a percent value or a fixed value. Percentage | Number
    bar_category_gap: Var[Union[str, int]]  # type: ignore

    # The gap between two bars in the same category, which can be a percent value or a fixed value. Percentage | Number
    bar_gap: Var[Union[str, int]]  # type: ignore

    # The width of all the bars in the chart. Number
    bar_size: Optional[Var[int]] = None

    # The maximum width of all the bars in a horizontal BarChart, or maximum height in a vertical BarChart.
    max_bar_size: Optional[Var[int]] = None

    # The type of offset function used to generate the lower and upper values in the series array. The four types are built-in offsets in d3-shape.
    stack_offset: Optional[Var[LiteralStackOffset]] = None

    # If false set, stacked items will be rendered left to right. If true set, stacked items will be rendered right to left. (Render direction affects SVG layering, not x position.)
    reverse_stack_order: Optional[Var[bool]] = None

    # Valid children components
    _valid_children: List[str] = [
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
    ]


class LineChart(ChartBase):
    """A Line chart component in Recharts."""

    tag: str = "LineChart"

    alias = "RechartsLineChart"

    # Valid children components
    _valid_children: List[str] = [
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
    ]


class ComposedChart(ChartBase):
    """A Composed chart component in Recharts."""

    tag: str = "ComposedChart"

    alias = "RechartsComposedChart"

    # The base value of area. Number | 'dataMin' | 'dataMax' | 'auto'
    base_value: Optional[Var[Union[int, LiteralComposedChartBaseValue]]] = None

    # The gap between two bar categories, which can be a percent value or a fixed value. Percentage | Number
    bar_category_gap: Var[Union[str, int]]  # type: ignore

    # The gap between two bars in the same category, which can be a percent value or a fixed value. Percentage | Number
    bar_gap: Optional[Var[int]] = None

    # The width of all the bars in the chart. Number
    bar_size: Optional[Var[int]] = None

    # If false set, stacked items will be rendered left to right. If true set, stacked items will be rendered right to left. (Render direction affects SVG layering, not x position.)
    reverse_stack_order: Optional[Var[bool]] = None

    # Valid children components
    _valid_children: List[str] = [
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
    ]


class PieChart(ChartBase):
    """A Pie chart component in Recharts."""

    tag: str = "PieChart"

    alias = "RechartsPieChart"

    # Valid children components
    _valid_children: List[str] = [
        "PolarAngleAxis",
        "PolarRadiusAxis",
        "PolarGrid",
        "Legend",
        "GraphingTooltip",
        "Pie",
    ]

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            EventTriggers.ON_CLICK: lambda: [],
            EventTriggers.ON_MOUSE_ENTER: lambda: [],
            EventTriggers.ON_MOUSE_LEAVE: lambda: [],
        }


class RadarChart(ChartBase):
    """A Radar chart component in Recharts."""

    tag: str = "RadarChart"

    alias = "RechartsRadarChart"

    # The The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of width. Number | Percentage
    cx: Optional[Var[Union[int, str]]] = None

    # The The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of height. Number | Percentage
    cy: Optional[Var[Union[int, str]]] = None

    # The angle of first radial direction line.
    start_angle: Optional[Var[int]] = None

    # The angle of last point in the circle which should be startAngle - 360 or startAngle + 360. We'll calculate the direction of chart by 'startAngle' and 'endAngle'.
    end_angle: Optional[Var[int]] = None

    # The inner radius of first circle grid. If set a percentage, the final value is obtained by multiplying the percentage of maxRadius which is calculated by the width, height, cx, cy. Number | Percentage
    inner_radius: Optional[Var[Union[int, str]]] = None

    # The outer radius of last circle grid. If set a percentage, the final value is obtained by multiplying the percentage of maxRadius which is calculated by the width, height, cx, cy. Number | Percentage
    outer_radius: Optional[Var[Union[int, str]]] = None

    # Valid children components
    _valid_children: List[str] = [
        "PolarAngleAxis",
        "PolarRadiusAxis",
        "PolarGrid",
        "Legend",
        "GraphingTooltip",
        "Radar",
    ]

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            EventTriggers.ON_CLICK: lambda: [],
            EventTriggers.ON_MOUSE_ENTER: lambda: [],
            EventTriggers.ON_MOUSE_MOVE: lambda: [],
            EventTriggers.ON_MOUSE_LEAVE: lambda: [],
        }


class RadialBarChart(ChartBase):
    """A RadialBar chart component in Recharts."""

    tag: str = "RadialBarChart"

    alias = "RechartsRadialBarChart"

    # The The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of width. Number | Percentage
    cx: Optional[Var[Union[int, str]]] = None

    # The The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of height. Number | Percentage
    cy: Optional[Var[Union[int, str]]] = None

    # The angle of first radial direction line.
    start_angle: Optional[Var[int]] = None

    # The angle of last point in the circle which should be startAngle - 360 or startAngle + 360. We'll calculate the direction of chart by 'startAngle' and 'endAngle'.
    end_angle: Optional[Var[int]] = None

    # The inner radius of first circle grid. If set a percentage, the final value is obtained by multiplying the percentage of maxRadius which is calculated by the width, height, cx, cy. Number | Percentage
    inner_radius: Optional[Var[Union[int, str]]] = None

    # The outer radius of last circle grid. If set a percentage, the final value is obtained by multiplying the percentage of maxRadius which is calculated by the width, height, cx, cy. Number | Percentage
    outer_radius: Optional[Var[Union[int, str]]] = None

    # The gap between two bar categories, which can be a percent value or a fixed value. Percentage | Number
    bar_category_gap: Optional[Var[Union[int, str]]] = None

    # The gap between two bars in the same category, which can be a percent value or a fixed value. Percentage | Number
    bar_gap: Optional[Var[str]] = None

    # The size of each bar. If the barSize is not specified, the size of bar will be calculated by the barCategoryGap, barGap and the quantity of bar groups.
    bar_size: Optional[Var[int]] = None

    # Valid children components
    _valid_children: List[str] = [
        "PolarAngleAxis",
        "PolarRadiusAxis",
        "PolarGrid",
        "Legend",
        "GraphingTooltip",
        "RadialBar",
    ]

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            EventTriggers.ON_CLICK: lambda: [],
            EventTriggers.ON_MOUSE_ENTER: lambda: [],
            EventTriggers.ON_MOUSE_MOVE: lambda: [],
            EventTriggers.ON_MOUSE_LEAVE: lambda: [],
        }


class ScatterChart(ChartBase):
    """A Scatter chart component in Recharts."""

    tag: str = "ScatterChart"

    alias = "RechartsScatterChart"

    # Valid children components
    _valid_children: List[str] = [
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
    ]

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            EventTriggers.ON_CLICK: lambda: [],
            EventTriggers.ON_MOUSE_OVER: lambda: [],
            EventTriggers.ON_MOUSE_OUT: lambda: [],
            EventTriggers.ON_MOUSE_ENTER: lambda: [],
            EventTriggers.ON_MOUSE_MOVE: lambda: [],
            EventTriggers.ON_MOUSE_LEAVE: lambda: [],
        }


class FunnelChart(RechartsCharts):
    """A Funnel chart component in Recharts."""

    tag: str = "FunnelChart"

    alias = "RechartsFunnelChart"

    # The source data, in which each element is an object.
    data: Optional[Var[List[Dict[str, Any]]]] = None

    # If any two categorical charts(rx.line_chart, rx.area_chart, rx.bar_chart, rx.composed_chart) have the same sync_id, these two charts can sync the position GraphingTooltip, and the start_index, end_index of Brush.
    sync_id: Optional[Var[str]] = None

    # When sync_id is provided, allows customisation of how the charts will synchronize GraphingTooltips and brushes. Using 'index' (default setting), other charts will reuse current datum's index within the data array. In cases where data does not have the same length, this might yield unexpected results. In that case use 'value' which will try to match other charts values, or a fully custom function which will receive tick, data as argument and should return an index. 'index' | 'value' | function
    sync_method: Optional[Var[str]] = None

    # The width of chart container. String or Integer
    width: Var[Union[str, int]] = "100%"  # type: ignore

    # The height of chart container.
    height: Var[Union[str, int]] = "100%"  # type: ignore

    # The layout of area in the chart. 'horizontal' | 'vertical'
    layout: Optional[Var[LiteralLayout]] = None

    # The sizes of whitespace around the chart.
    margin: Optional[Var[Dict[str, Any]]] = None

    # The type of offset function used to generate the lower and upper values in the series array. The four types are built-in offsets in d3-shape. 'expand' | 'none' | 'wiggle' | 'silhouette'
    stack_offset: Optional[Var[LiteralStackOffset]] = None

    # The layout of bars in the chart. centeric
    layout: Optional[Var[str]] = None

    # Valid children components
    _valid_children: List[str] = ["Legend", "GraphingTooltip", "Funnel"]

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            EventTriggers.ON_CLICK: lambda: [],
            EventTriggers.ON_MOUSE_ENTER: lambda: [],
            EventTriggers.ON_MOUSE_MOVE: lambda: [],
            EventTriggers.ON_MOUSE_LEAVE: lambda: [],
        }


class Treemap(RechartsCharts):
    """A Treemap chart component in Recharts."""

    tag: str = "Treemap"

    alias = "RechartsTreemap"

    # The width of chart container. String or Integer
    width: Var[Union[str, int]] = "100%"  # type: ignore

    # The height of chart container.
    height: Var[Union[str, int]] = "100%"  # type: ignore

    # data of treemap. Array
    data: Optional[Var[List[Dict[str, Any]]]] = None

    # The key of a group of data which should be unique in a treemap. String | Number | Function
    data_key: Optional[Var[Union[str, int]]] = None

    # The treemap will try to keep every single rectangle's aspect ratio near the aspectRatio given. Number
    aspect_ratio: Optional[Var[int]] = None

    # If set false, animation of area will be disabled.
    is_animation_active: Optional[Var[bool]] = None

    # Specifies when the animation should begin, the unit of this option is ms.
    animation_begin: Optional[Var[int]] = None

    # Specifies the duration of animation, the unit of this option is ms.
    animation_duration: Optional[Var[int]] = None

    # The type of easing function. 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'linear'
    animation_easing: Optional[Var[LiteralAnimationEasing]] = None

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
