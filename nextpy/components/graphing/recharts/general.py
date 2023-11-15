"""General components for Recharts."""
from __future__ import annotations

from typing import Any, Dict, List, Union

from nextpy.constants import EventTriggers
from nextpy.core.vars import Var

from .recharts import (
    LiteralIconType,
    LiteralLayout,
    LiteralLegendAlign,
    LiteralPosition,
    LiteralVerticalAlign,
    Recharts,
)


class ResponsiveContainer(Recharts):
    """A base class for responsive containers in Recharts."""

    tag = "ResponsiveContainer"

    alias = "RechartsResponsiveContainer"

    # The aspect ratio of the container. The final aspect ratio of the SVG element will be (width / height) * aspect. Number
    aspect: Var[int]

    # The width of chart container. Can be a number or string
    width: Var[Union[int, str]]

    # The height of chart container. Number
    height: Var[Union[int, str]]

    # The minimum width of chart container.
    min_width: Var[int]

    # The minimum height of chart container. Number
    min_height: Var[int]

    # If specified a positive number, debounced function will be used to handle the resize event.
    debounce: Var[int]

    # Valid children components
    valid_children: List[str] = [
        "AreaChart",
        "BarChart",
        "LineChart",
        "PieChart",
        "RadarChart",
        "RadialBarChart",
        "ScatterChart",
        "Treemap",
        "ComposedChart",
    ]


class Legend(Recharts):
    """A Legend component in Recharts."""

    tag = "Legend"

    alias = "RechartsLegend"

    # The width of legend container. Number
    width: Var[int]

    # The height of legend container. Number
    height: Var[int]

    # The layout of legend items. 'horizontal' | 'vertical'
    layout: Var[LiteralLayout]

    # The alignment of legend items in 'horizontal' direction, which can be 'left', 'center', 'right'.
    align: Var[LiteralLegendAlign]

    # The alignment of legend items in 'vertical' direction, which can be 'top', 'middle', 'bottom'.
    vertical_align: Var[LiteralVerticalAlign]

    # The size of icon in each legend item.
    icon_size: Var[int]

    # The type of icon in each legend item. 'line' | 'plainline' | 'square' | 'rect' | 'circle' | 'cross' | 'diamond' | 'star' | 'triangle' | 'wye'
    icon_type: Var[LiteralIconType]

    # The width of chart container, usually calculated internally.
    chart_width: Var[int]

    # The height of chart container, usually calculated internally.
    chart_height: Var[int]

    # The margin of chart container, usually calculated internally.
    margin: Var[Dict[str, Any]]

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


class GraphingTooltip(Recharts):
    """A Tooltip component in Recharts."""

    tag = "Tooltip"

    alias = "RechartsTooltip"

    # The separator between name and value.
    separator: Var[str]

    # The offset size of tooltip. Number
    offset: Var[int]

    # When an item of the payload has value null or undefined, this item won't be displayed.
    filter_null: Var[bool]

    # If set false, no cursor will be drawn when tooltip is active.
    cursor: Var[bool]

    # The box of viewing area, which has the shape of {x: someVal, y: someVal, width: someVal, height: someVal}, usually calculated internally.
    view_box: Var[Dict[str, Any]]

    # If set true, the tooltip is displayed. If set false, the tooltip is hidden, usually calculated internally.
    active: Var[bool]

    # If this field is set, the tooltip position will be fixed and will not move anymore.
    position: Var[Dict[str, Any]]

    # The coordinate of tooltip which is usually calculated internally.
    coordinate: Var[Dict[str, Any]]


class Label(Recharts):
    """A Label component in Recharts."""

    tag = "Label"

    alias = "RechartsLabel"

    # The box of viewing area, which has the shape of {x: someVal, y: someVal, width: someVal, height: someVal}, usually calculated internally.
    view_box: Var[Dict[str, Any]]

    # The value of label, which can be specified by this props or the children of <Label />
    value: Var[str]

    # The offset of label which can be specified by this props or the children of <Label />
    offset: Var[int]

    # The position of label which can be specified by this props or the children of <Label />
    position: Var[LiteralPosition]


class LabelList(Recharts):
    """A LabelList component in Recharts."""

    tag = "LabelList"

    alias = "RechartsLabelList"

    # The key of a group of label values in data.
    data_key: Var[Union[str, int]]

    # The position of each label relative to it view box。"Top" | "left" | "right" | "bottom" | "inside" | "outside" | "insideLeft" | "insideRight" | "insideTop" | "insideBottom" | "insideTopLeft" | "insideBottomLeft" | "insideTopRight" | "insideBottomRight" | "insideStart" | "insideEnd" | "end" | "center"
    position: Var[LiteralPosition]

    # The offset to the specified "position"
    offset: Var[int]

    # Color of the fill
    fill: Var[str]

    # Color of the stroke
    stroke: Var[str]
