"""General components for Recharts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from reflex_base.components.component import MemoizationLeaf, field
from reflex_base.constants.colors import Color
from reflex_base.event import EventHandler, no_args_event_spec
from reflex_base.vars.base import LiteralVar, Var

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

    aspect: Var[int] = field(
        doc="The aspect ratio of the container. The final aspect ratio of the SVG element will be (width / height) * aspect. Number"
    )

    width: Var[int | str] = field(
        doc='The width of chart container. Can be a number or string. Default: "100%"'
    )

    height: Var[int | str] = field(
        doc='The height of chart container. Can be a number or string. Default: "100%"'
    )

    min_width: Var[int | str] = field(
        doc="The minimum width of chart container. Number or string."
    )

    min_height: Var[int | str] = field(
        doc="The minimum height of chart container. Number or string."
    )

    debounce: Var[int] = field(
        doc="If specified a positive number, debounced function will be used to handle the resize event. Default: 0"
    )

    on_resize: EventHandler[no_args_event_spec] = field(
        doc="If specified provides a callback providing the updated chart width and height values."
    )

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

    width: Var[int] = field(doc="The width of legend container. Number")

    height: Var[int] = field(doc="The height of legend container. Number")

    layout: Var[LiteralLayout] = field(
        doc="The layout of legend items. 'horizontal' | 'vertical'. Default: \"horizontal\""
    )

    align: Var[LiteralLegendAlign] = field(
        doc="The alignment of legend items in 'horizontal' direction, which can be 'left', 'center', 'right'. Default: \"center\""
    )

    vertical_align: Var[LiteralVerticalAlign] = field(
        doc="The alignment of legend items in 'vertical' direction, which can be 'top', 'middle', 'bottom'. Default: \"bottom\""
    )

    icon_size: Var[int] = field(doc="The size of icon in each legend item. Default: 14")

    icon_type: Var[LiteralIconType] = field(
        doc="The type of icon in each legend item. 'line' | 'plainline' | 'square' | 'rect' | 'circle' | 'cross' | 'diamond' | 'star' | 'triangle' | 'wye'"
    )

    payload: Var[Sequence[dict[str, Any]]] = field(
        doc="The source data of the content to be displayed in the legend, usually calculated internally. Default: []"
    )

    chart_width: Var[int] = field(
        doc="The width of chart container, usually calculated internally."
    )

    chart_height: Var[int] = field(
        doc="The height of chart container, usually calculated internally."
    )

    margin: Var[dict[str, Any]] = field(
        doc="The margin of chart container, usually calculated internally."
    )

    on_click: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of click on the items in this group"
    )

    on_mouse_down: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mousedown on the items in this group"
    )

    on_mouse_up: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseup on the items in this group"
    )

    on_mouse_move: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mousemove on the items in this group"
    )

    on_mouse_over: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseover on the items in this group"
    )

    on_mouse_out: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseout on the items in this group"
    )

    on_mouse_enter: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseenter on the items in this group"
    )

    on_mouse_leave: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseleave on the items in this group"
    )


class GraphingTooltip(Recharts):
    """A Tooltip component in Recharts."""

    tag = "Tooltip"

    alias = "RechartsTooltip"

    separator: Var[str] = field(
        doc='The separator between name and value. Default: ":"'
    )

    offset: Var[int] = field(doc="The offset size of tooltip. Number. Default: 10")

    filter_null: Var[bool] = field(
        doc="When an item of the payload has value null or undefined, this item won't be displayed. Default: True"
    )

    cursor: Var[dict[str, Any] | bool] = field(
        default=LiteralVar.create({
            "strokeWidth": 1,
            "fill": Color("gray", 3),
        }),
        doc='If set false, no cursor will be drawn when tooltip is active. Default: {"strokeWidth": 1, "fill": rx.color("gray", 3)}',
    )

    view_box: Var[dict[str, Any]] = field(
        doc="The box of viewing area, which has the shape of {x: someVal, y: someVal, width: someVal, height: someVal}, usually calculated internally."
    )

    item_style: Var[dict[str, Any]] = field(
        default=LiteralVar.create({
            "color": Color("gray", 12),
        }),
        doc='The style of default tooltip content item which is a li element. Default: {"color": rx.color("gray", 12)}',
    )

    wrapper_style: Var[dict[str, Any]] = field(
        doc="The style of tooltip wrapper which is a dom element. Default: {}"
    )

    content_style: Var[dict[str, Any]] = field(
        default=LiteralVar.create({
            "background": Color("gray", 1),
            "borderColor": Color("gray", 4),
            "borderRadius": "8px",
        }),
        doc='The style of tooltip content which is a dom element. Default: {"background": rx.color("gray", 1), "borderColor": rx.color("gray", 4), "borderRadius": "8px"}',
    )

    label_style: Var[dict[str, Any]] = field(
        default=LiteralVar.create({"color": Color("gray", 11)}),
        doc='The style of default tooltip label which is a p element. Default: {"color": rx.color("gray", 11)}',
    )

    allow_escape_view_box: Var[dict[str, bool]] = field(
        doc='This option allows the tooltip to extend beyond the viewBox of the chart itself. Default: {"x": False, "y": False}'
    )

    active: Var[bool] = field(
        doc="If set true, the tooltip is displayed. If set false, the tooltip is hidden, usually calculated internally. Default: False"
    )

    position: Var[dict[str, Any]] = field(
        doc="If this field is set, the tooltip position will be fixed and will not move anymore."
    )

    coordinate: Var[dict[str, Any]] = field(
        doc='The coordinate of tooltip which is usually calculated internally. Default: {"x": 0, "y": 0}'
    )

    is_animation_active: Var[bool] = field(
        doc="If set false, animation of tooltip will be disabled. Default: True"
    )

    animation_duration: Var[int] = field(
        doc="Specifies the duration of animation, the unit of this option is ms. Default: 1500"
    )

    animation_easing: Var[LiteralAnimationEasing] = field(
        doc='The type of easing function. Default: "ease"'
    )


class Label(Recharts):
    """A Label component in Recharts."""

    tag = "Label"

    alias = "RechartsLabel"

    view_box: Var[dict[str, Any]] = field(
        doc="The box of viewing area, which has the shape of {x: someVal, y: someVal, width: someVal, height: someVal}, usually calculated internally."
    )

    value: Var[str] = field(
        doc="The value of label, which can be specified by this props or the children of <Label />"
    )

    offset: Var[int] = field(
        doc="The offset of label which can be specified by this props or the children of <Label />"
    )

    position: Var[LiteralPosition] = field(
        doc="The position of label which can be specified by this props or the children of <Label />"
    )


class LabelList(Recharts):
    """A LabelList component in Recharts."""

    tag = "LabelList"

    alias = "RechartsLabelList"

    data_key: Var[str | int] = field(doc="The key of a group of label values in data.")

    position: Var[LiteralPosition] = field(
        doc='The position of each label relative to it view box. "Top" | "left" | "right" | "bottom" | "inside" | "outside" | "insideLeft" | "insideRight" | "insideTop" | "insideBottom" | "insideTopLeft" | "insideBottomLeft" | "insideTopRight" | "insideBottomRight" | "insideStart" | "insideEnd" | "end" | "center"'
    )

    offset: Var[int] = field(doc='The offset to the specified "position". Default: 5')

    fill: Var[str | Color] = field(
        default=LiteralVar.create(Color("gray", 10)),
        doc='The fill color of each label. Default: rx.color("gray", 10)',
    )

    stroke: Var[str | Color] = field(
        default=LiteralVar.create("none"),
        doc='The stroke color of each label. Default: "none"',
    )


class Cell(Recharts):
    """A Cell component in Recharts."""

    tag = "Cell"

    alias = "RechartsCell"

    fill: Var[str | Color] = field(
        doc="The presentation attribute of a rectangle in bar or a sector in pie."
    )

    stroke: Var[str | Color] = field(
        doc="The presentation attribute of a rectangle in bar or a sector in pie."
    )


responsive_container = ResponsiveContainer.create
legend = Legend.create
graphing_tooltip = tooltip = GraphingTooltip.create
label = Label.create
label_list = LabelList.create
cell = Cell.create
