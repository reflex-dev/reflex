"""General components for Recharts."""

from __future__ import annotations

from typing import Any, Dict, List, Union

from reflex.components.component import MemoizationLeaf
from reflex.event import EventHandler
from reflex.vars import Var

from .recharts import (
    LiteralAnimationEasing,
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
        "FunnelChart",
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

    # The customized event handler of click on the items in this group
    on_click: EventHandler[lambda: []]

    # The customized event handler of mousedown on the items in this group
    on_mouse_down: EventHandler[lambda: []]

    # The customized event handler of mouseup on the items in this group
    on_mouse_up: EventHandler[lambda: []]

    # The customized event handler of mousemove on the items in this group
    on_mouse_move: EventHandler[lambda: []]

    # The customized event handler of mouseover on the items in this group
    on_mouse_over: EventHandler[lambda: []]

    # The customized event handler of mouseout on the items in this group
    on_mouse_out: EventHandler[lambda: []]

    # The customized event handler of mouseenter on the items in this group
    on_mouse_enter: EventHandler[lambda: []]

    # The customized event handler of mouseleave on the items in this group
    on_mouse_leave: EventHandler[lambda: []]


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

    # The style of default tooltip content item which is a li element. DEFAULT: {}
    item_style: Var[Dict[str, Any]]

    # The style of tooltip wrapper which is a dom element. DEFAULT: {}
    wrapper_style: Var[Dict[str, Any]]

    # The style of tooltip content which is a dom element. DEFAULT: {}
    content_style: Var[Dict[str, Any]]

    # The style of default tooltip label which is a p element. DEFAULT: {}
    label_style: Var[Dict[str, Any]]

    # This option allows the tooltip to extend beyond the viewBox of the chart itself. DEFAULT: { x: false, y: false }
    allow_escape_view_box: Var[Dict[str, bool]] = Var.create_safe(
        {"x": False, "y": False}
    )

    # If set true, the tooltip is displayed. If set false, the tooltip is hidden, usually calculated internally.
    active: Var[bool]

    # If this field is set, the tooltip position will be fixed and will not move anymore.
    position: Var[Dict[str, Any]]

    # The coordinate of tooltip which is usually calculated internally.
    coordinate: Var[Dict[str, Any]]

    # If set false, animation of tooltip will be disabled. DEFAULT: true in CSR, and false in SSR
    is_animation_active: Var[bool]

    # Specifies the duration of animation, the unit of this option is ms. DEFAULT: 1500
    animation_duration: Var[int]

    # The type of easing function. DEFAULT: 'ease'
    animation_easing: Var[LiteralAnimationEasing]


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


responsive_container = ResponsiveContainer.create
legend = Legend.create
graphing_tooltip = GraphingTooltip.create
label = Label.create
label_list = LabelList.create
