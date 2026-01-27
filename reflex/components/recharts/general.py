"""General components for Recharts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from reflex.components.component import MemoizationLeaf
from reflex.constants.colors import Color
from reflex.event import EventHandler, no_args_event_spec
from reflex.vars.base import LiteralVar, Var

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

    # The width of chart container. Can be a number or string. Default: "100%"
    width: Var[int | str]

    # The height of chart container. Can be a number or string. Default: "100%"
    height: Var[int | str]

    # The minimum width of chart container. Number or string.
    min_width: Var[int | str]

    # The minimum height of chart container. Number or string.
    min_height: Var[int | str]

    # If specified a positive number, debounced function will be used to handle the resize event. Default: 0
    debounce: Var[int]

    # If specified provides a callback providing the updated chart width and height values.
    on_resize: EventHandler[no_args_event_spec]

    # Valid children components
    _valid_children: ClassVar[list[str]] = [
        "AreaChart",
        "BarChart",
        "LineChart",
        "PieChart",
        "RadarChart",
        "RadialBarChart",
        "ResponsiveContainer",
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

    # The layout of legend items. 'horizontal' | 'vertical'. Default: "horizontal"
    layout: Var[LiteralLayout]

    # The alignment of legend items in 'horizontal' direction, which can be 'left', 'center', 'right'. Default: "center"
    align: Var[LiteralLegendAlign]

    # The alignment of legend items in 'vertical' direction, which can be 'top', 'middle', 'bottom'. Default: "bottom"
    vertical_align: Var[LiteralVerticalAlign]

    # The size of icon in each legend item. Default: 14
    icon_size: Var[int]

    # The type of icon in each legend item. 'line' | 'plainline' | 'square' | 'rect' | 'circle' | 'cross' | 'diamond' | 'star' | 'triangle' | 'wye'
    icon_type: Var[LiteralIconType]

    # The source data of the content to be displayed in the legend, usually calculated internally. Default: []
    payload: Var[Sequence[dict[str, Any]]]

    # The width of chart container, usually calculated internally.
    chart_width: Var[int]

    # The height of chart container, usually calculated internally.
    chart_height: Var[int]

    # The margin of chart container, usually calculated internally.
    margin: Var[dict[str, Any]]

    # The customized event handler of click on the items in this group
    on_click: EventHandler[no_args_event_spec]

    # The customized event handler of mousedown on the items in this group
    on_mouse_down: EventHandler[no_args_event_spec]

    # The customized event handler of mouseup on the items in this group
    on_mouse_up: EventHandler[no_args_event_spec]

    # The customized event handler of mousemove on the items in this group
    on_mouse_move: EventHandler[no_args_event_spec]

    # The customized event handler of mouseover on the items in this group
    on_mouse_over: EventHandler[no_args_event_spec]

    # The customized event handler of mouseout on the items in this group
    on_mouse_out: EventHandler[no_args_event_spec]

    # The customized event handler of mouseenter on the items in this group
    on_mouse_enter: EventHandler[no_args_event_spec]

    # The customized event handler of mouseleave on the items in this group
    on_mouse_leave: EventHandler[no_args_event_spec]


class GraphingTooltip(Recharts):
    """A Tooltip component in Recharts."""

    tag = "Tooltip"

    alias = "RechartsTooltip"

    # The separator between name and value. Default: ":"
    separator: Var[str]

    # The offset size of tooltip. Number. Default: 10
    offset: Var[int]

    # When an item of the payload has value null or undefined, this item won't be displayed. Default: True
    filter_null: Var[bool]

    # If set false, no cursor will be drawn when tooltip is active. Default: {"strokeWidth": 1, "fill": rx.color("gray", 3)}
    cursor: Var[dict[str, Any] | bool] = LiteralVar.create({
        "strokeWidth": 1,
        "fill": Color("gray", 3),
    })

    # The box of viewing area, which has the shape of {x: someVal, y: someVal, width: someVal, height: someVal}, usually calculated internally.
    view_box: Var[dict[str, Any]]

    # The style of default tooltip content item which is a li element. Default: {"color": rx.color("gray", 12)}
    item_style: Var[dict[str, Any]] = LiteralVar.create({
        "color": Color("gray", 12),
    })

    # The style of tooltip wrapper which is a dom element. Default: {}
    wrapper_style: Var[dict[str, Any]]

    # The style of tooltip content which is a dom element. Default: {"background": rx.color("gray", 1), "borderColor": rx.color("gray", 4), "borderRadius": "8px"}
    content_style: Var[dict[str, Any]] = LiteralVar.create({
        "background": Color("gray", 1),
        "borderColor": Color("gray", 4),
        "borderRadius": "8px",
    })

    # The style of default tooltip label which is a p element. Default: {"color": rx.color("gray", 11)}
    label_style: Var[dict[str, Any]] = LiteralVar.create({"color": Color("gray", 11)})

    # This option allows the tooltip to extend beyond the viewBox of the chart itself. Default: {"x": False, "y": False}
    allow_escape_view_box: Var[dict[str, bool]]

    # If set true, the tooltip is displayed. If set false, the tooltip is hidden, usually calculated internally. Default: False
    active: Var[bool]

    # If this field is set, the tooltip position will be fixed and will not move anymore.
    position: Var[dict[str, Any]]

    # The coordinate of tooltip which is usually calculated internally. Default: {"x": 0, "y": 0}
    coordinate: Var[dict[str, Any]]

    # If set false, animation of tooltip will be disabled. Default: True
    is_animation_active: Var[bool]

    # Specifies the duration of animation, the unit of this option is ms. Default: 1500
    animation_duration: Var[int]

    # The type of easing function. Default: "ease"
    animation_easing: Var[LiteralAnimationEasing]


class Label(Recharts):
    """A Label component in Recharts."""

    tag = "Label"

    alias = "RechartsLabel"

    # The box of viewing area, which has the shape of {x: someVal, y: someVal, width: someVal, height: someVal}, usually calculated internally.
    view_box: Var[dict[str, Any]]

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
    data_key: Var[str | int]

    # The position of each label relative to it view box. "Top" | "left" | "right" | "bottom" | "inside" | "outside" | "insideLeft" | "insideRight" | "insideTop" | "insideBottom" | "insideTopLeft" | "insideBottomLeft" | "insideTopRight" | "insideBottomRight" | "insideStart" | "insideEnd" | "end" | "center"
    position: Var[LiteralPosition]

    # The offset to the specified "position". Default: 5
    offset: Var[int]

    # The fill color of each label. Default: rx.color("gray", 10)
    fill: Var[str | Color] = LiteralVar.create(Color("gray", 10))

    # The stroke color of each label. Default: "none"
    stroke: Var[str | Color] = LiteralVar.create("none")


class Cell(Recharts):
    """A Cell component in Recharts."""

    tag = "Cell"

    alias = "RechartsCell"

    # The presentation attribute of a rectangle in bar or a sector in pie.
    fill: Var[str | Color]

    # The presentation attribute of a rectangle in bar or a sector in pie.
    stroke: Var[str | Color]


responsive_container = ResponsiveContainer.create
legend = Legend.create
graphing_tooltip = tooltip = GraphingTooltip.create
label = Label.create
label_list = LabelList.create
cell = Cell.create
