"""General components for Recharts."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from reflex.components.component import MemoizationLeaf
from reflex.constants import EventTriggers
from reflex.vars import Var

from .recharts import (
    LiteralIconType,
    LiteralLayout,
    LiteralLegendAlign,
    LiteralPosition,
    LiteralVerticalAlign,
    Recharts,
)


class ResponsiveContainer(Recharts, MemoizationLeaf):
    """A base class for responsive containers in Recharts."""

    tag = "ResponsiveContainer"

    alias = "RechartsResponsiveContainer"

    # The aspect ratio of the container. The final aspect ratio of the SVG element will be (width / height) * aspect. Number
    aspect: Optional[Var[int]] = None

    # The width of chart container. Can be a number or string
    width: Optional[Var[Union[int, str]]] = None

    # The height of chart container. Number
    height: Optional[Var[Union[int, str]]] = None

    # The minimum width of chart container.
    min_width: Optional[Var[int]] = None

    # The minimum height of chart container. Number
    min_height: Optional[Var[int]] = None

    # If specified a positive number, debounced function will be used to handle the resize event.
    debounce: Optional[Var[int]] = None

    # Valid children components
    _valid_children: List[str] = [
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
    width: Optional[Var[int]] = None

    # The height of legend container. Number
    height: Optional[Var[int]] = None

    # The layout of legend items. 'horizontal' | 'vertical'
    layout: Optional[Var[LiteralLayout]] = None

    # The alignment of legend items in 'horizontal' direction, which can be 'left', 'center', 'right'.
    align: Optional[Var[LiteralLegendAlign]] = None

    # The alignment of legend items in 'vertical' direction, which can be 'top', 'middle', 'bottom'.
    vertical_align: Optional[Var[LiteralVerticalAlign]] = None

    # The size of icon in each legend item.
    icon_size: Optional[Var[int]] = None

    # The type of icon in each legend item. 'line' | 'plainline' | 'square' | 'rect' | 'circle' | 'cross' | 'diamond' | 'star' | 'triangle' | 'wye'
    icon_type: Optional[Var[LiteralIconType]] = None

    # The width of chart container, usually calculated internally.
    chart_width: Optional[Var[int]] = None

    # The height of chart container, usually calculated internally.
    chart_height: Optional[Var[int]] = None

    # The margin of chart container, usually calculated internally.
    margin: Optional[Var[Dict[str, Any]]] = None

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
    separator: Optional[Var[str]] = None

    # The offset size of tooltip. Number
    offset: Optional[Var[int]] = None

    # When an item of the payload has value null or undefined, this item won't be displayed.
    filter_null: Optional[Var[bool]] = None

    # If set false, no cursor will be drawn when tooltip is active.
    cursor: Optional[Var[bool]] = None

    # The box of viewing area, which has the shape of {x: someVal, y: someVal, width: someVal, height: someVal}, usually calculated internally.
    view_box: Optional[Var[Dict[str, Any]]] = None

    # If set true, the tooltip is displayed. If set false, the tooltip is hidden, usually calculated internally.
    active: Optional[Var[bool]] = None

    # If this field is set, the tooltip position will be fixed and will not move anymore.
    position: Optional[Var[Dict[str, Any]]] = None

    # The coordinate of tooltip which is usually calculated internally.
    coordinate: Optional[Var[Dict[str, Any]]] = None


class Label(Recharts):
    """A Label component in Recharts."""

    tag = "Label"

    alias = "RechartsLabel"

    # The box of viewing area, which has the shape of {x: someVal, y: someVal, width: someVal, height: someVal}, usually calculated internally.
    view_box: Optional[Var[Dict[str, Any]]] = None

    # The value of label, which can be specified by this props or the children of <Label />
    value: Optional[Var[str]] = None

    # The offset of label which can be specified by this props or the children of <Label />
    offset: Optional[Var[int]] = None

    # The position of label which can be specified by this props or the children of <Label />
    position: Optional[Var[LiteralPosition]] = None


class LabelList(Recharts):
    """A LabelList component in Recharts."""

    tag = "LabelList"

    alias = "RechartsLabelList"

    # The key of a group of label values in data.
    data_key: Optional[Var[Union[str, int]]] = None

    # The position of each label relative to it view box。"Top" | "left" | "right" | "bottom" | "inside" | "outside" | "insideLeft" | "insideRight" | "insideTop" | "insideBottom" | "insideTopLeft" | "insideBottomLeft" | "insideTopRight" | "insideBottomRight" | "insideStart" | "insideEnd" | "end" | "center"
    position: Optional[Var[LiteralPosition]] = None

    # The offset to the specified "position"
    offset: Optional[Var[int]] = None

    # Color of the fill
    fill: Optional[Var[str]] = None

    # Color of the stroke
    stroke: Optional[Var[str]] = None
