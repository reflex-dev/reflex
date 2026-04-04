"""Polar charts in Recharts."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from reflex_base.components.component import field
from reflex_base.constants import EventTriggers
from reflex_base.constants.colors import Color
from reflex_base.event import EventHandler, no_args_event_spec
from reflex_base.vars.base import LiteralVar, Var

from .recharts import (
    ACTIVE_DOT_TYPE,
    LiteralAnimationEasing,
    LiteralGridType,
    LiteralLegendType,
    LiteralOrientationLeftRightMiddle,
    LiteralPolarRadiusType,
    LiteralScale,
    Recharts,
)


class Pie(Recharts):
    """A Pie chart component in Recharts."""

    tag = "Pie"

    alias = "RechartsPie"

    data: Var[Sequence[dict[str, Any]]] = field(
        doc="The source data which each element is an object."
    )

    data_key: Var[str | int] = field(doc="The key of each sector's value.")

    cx: Var[int | str] = field(
        doc='The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container width. Default: "50%"'
    )

    cy: Var[int | str] = field(
        doc='The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container height. Default: "50%"'
    )

    inner_radius: Var[int | str] = field(
        doc="The inner radius of pie, which can be set to a percent value. Default: 0"
    )

    outer_radius: Var[int | str] = field(
        doc='The outer radius of pie, which can be set to a percent value. Default: "80%"'
    )

    start_angle: Var[int] = field(doc="The angle of first sector. Default: 0")

    end_angle: Var[int] = field(
        doc="The end angle of last sector, which should be unequal to start_angle. Default: 360"
    )

    min_angle: Var[int] = field(doc="The minimum angle of each unzero data. Default: 0")

    padding_angle: Var[int] = field(doc="The angle between two sectors. Default: 0")

    name_key: Var[str] = field(doc='The key of each sector\'s name. Default: "name"')

    legend_type: Var[LiteralLegendType] = field(
        doc="The type of icon in legend. If set to 'none', no legend item will be rendered. Default: \"rect\""
    )

    label: Var[bool | dict[str, Any]] = field(
        default=Var.create(False),
        doc="If false set, labels will not be drawn. If true set, labels will be drawn which have the props calculated internally. Default: False",
    )

    label_line: Var[bool | dict[str, Any]] = field(
        doc="If false set, label lines will not be drawn. If true set, label lines will be drawn which have the props calculated internally. Default: False"
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = ["Cell", "LabelList", "Bare"]

    stroke: Var[str | Color] = field(
        default=LiteralVar.create(Color("accent", 9)),
        doc='Stoke color. Default: rx.color("accent", 9)',
    )

    fill: Var[str | Color] = field(
        default=LiteralVar.create(Color("accent", 3)),
        doc='Fill color. Default: rx.color("accent", 3)',
    )

    is_animation_active: Var[bool] = field(
        doc="If set false, animation of tooltip will be disabled. Default: true in CSR, and false in SSR"
    )

    animation_begin: Var[int] = field(
        doc="Specifies when the animation should begin, the unit of this option is ms. Default: 400"
    )

    animation_duration: Var[int] = field(
        doc="Specifies the duration of animation, the unit of this option is ms. Default: 1500"
    )

    animation_easing: Var[LiteralAnimationEasing] = field(
        doc='The type of easing function. Default: "ease"'
    )

    root_tab_index: Var[int] = field(
        doc="The tabindex of wrapper surrounding the cells. Default: 0"
    )

    @classmethod
    def get_event_triggers(cls) -> dict[str, Var | Any]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            EventTriggers.ON_ANIMATION_START: no_args_event_spec,
            EventTriggers.ON_ANIMATION_END: no_args_event_spec,
            EventTriggers.ON_CLICK: no_args_event_spec,
            EventTriggers.ON_MOUSE_MOVE: no_args_event_spec,
            EventTriggers.ON_MOUSE_OVER: no_args_event_spec,
            EventTriggers.ON_MOUSE_OUT: no_args_event_spec,
            EventTriggers.ON_MOUSE_ENTER: no_args_event_spec,
            EventTriggers.ON_MOUSE_LEAVE: no_args_event_spec,
        }


class Radar(Recharts):
    """A Radar chart component in Recharts."""

    tag = "Radar"

    alias = "RechartsRadar"

    data_key: Var[str | int] = field(
        doc="The key of a group of data which should be unique in a radar chart."
    )

    points: Var[Sequence[dict[str, Any]]] = field(
        doc="The coordinates of all the vertices of the radar shape, like [{ x, y }]."
    )

    dot: Var[ACTIVE_DOT_TYPE] = field(
        doc="If false set, dots will not be drawn. Default: True"
    )

    stroke: Var[str | Color] = field(
        default=LiteralVar.create(Color("accent", 9)),
        doc='Stoke color. Default: rx.color("accent", 9)',
    )

    fill: Var[str | Color] = field(
        default=LiteralVar.create(Color("accent", 3)),
        doc='Fill color. Default: rx.color("accent", 3)',
    )

    fill_opacity: Var[float] = field(
        default=LiteralVar.create(0.6),
        doc="The opacity to fill the chart. Default: 0.6",
    )

    legend_type: Var[LiteralLegendType] = field(
        doc="The type of icon in legend. If set to 'none', no legend item will be rendered. Default: \"rect\""
    )

    label: Var[bool | dict[str, Any]] = field(
        doc="If false set, labels will not be drawn. Default: True"
    )

    is_animation_active: Var[bool] = field(
        doc="If set false, animation of polygon will be disabled. Default: True in CSR, and False in SSR"
    )

    animation_begin: Var[int] = field(
        doc="Specifies when the animation should begin, the unit of this option is ms. Default: 0"
    )

    animation_duration: Var[int] = field(
        doc="Specifies the duration of animation, the unit of this option is ms. Default: 1500"
    )

    animation_easing: Var[LiteralAnimationEasing] = field(
        doc="The type of easing function. 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'linear'. Default: \"ease\""
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = ["LabelList"]

    @classmethod
    def get_event_triggers(cls) -> dict[str, Var | Any]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            EventTriggers.ON_ANIMATION_START: no_args_event_spec,
            EventTriggers.ON_ANIMATION_END: no_args_event_spec,
        }


class RadialBar(Recharts):
    """A RadialBar chart component in Recharts."""

    tag = "RadialBar"

    alias = "RechartsRadialBar"

    data: Var[Sequence[dict[str, Any]]] = field(
        doc="The source data which each element is an object."
    )

    data_key: Var[str | int] = field(
        doc="The key of a group of data which should be unique to show the meaning of angle axis."
    )

    min_angle: Var[int] = field(
        doc="Min angle of each bar. A positive value between 0 and 360. Default: 0"
    )

    legend_type: Var[LiteralLegendType] = field(
        doc="The type of icon in legend. If set to 'none', no legend item will be rendered. Default: \"rect\""
    )

    label: Var[bool | dict[str, Any]] = field(
        doc="If false set, labels will not be drawn. If true set, labels will be drawn which have the props calculated internally. Default: False"
    )

    background: Var[bool | dict[str, Any]] = field(
        doc="If false set, background sector will not be drawn. Default: False"
    )

    is_animation_active: Var[bool] = field(
        doc="If set false, animation of radial bars will be disabled. Default: True"
    )

    animation_begin: Var[int] = field(
        doc="Specifies when the animation should begin, the unit of this option is ms. Default: 0"
    )

    animation_duration: Var[int] = field(
        doc="Specifies the duration of animation, the unit of this option is ms. Default 1500"
    )

    animation_easing: Var[LiteralAnimationEasing] = field(
        doc="The type of easing function. 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'linear'. Default: \"ease\""
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = ["Cell", "LabelList"]

    @classmethod
    def get_event_triggers(cls) -> dict[str, Var | Any]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            EventTriggers.ON_CLICK: no_args_event_spec,
            EventTriggers.ON_MOUSE_MOVE: no_args_event_spec,
            EventTriggers.ON_MOUSE_OVER: no_args_event_spec,
            EventTriggers.ON_MOUSE_OUT: no_args_event_spec,
            EventTriggers.ON_MOUSE_ENTER: no_args_event_spec,
            EventTriggers.ON_MOUSE_LEAVE: no_args_event_spec,
            EventTriggers.ON_ANIMATION_START: no_args_event_spec,
            EventTriggers.ON_ANIMATION_END: no_args_event_spec,
        }


class PolarAngleAxis(Recharts):
    """A PolarAngleAxis component in Recharts."""

    tag = "PolarAngleAxis"

    alias = "RechartsPolarAngleAxis"

    data_key: Var[str | int] = field(
        doc="The key of a group of data which should be unique to show the meaning of angle axis."
    )

    cx: Var[int | str] = field(
        doc="The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container width."
    )

    cy: Var[int | str] = field(
        doc="The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container height."
    )

    radius: Var[int | str] = field(
        doc="The outer radius of circle grid. If set a percentage, the final value is obtained by multiplying the percentage of maxRadius which is calculated by the width, height, cx, cy."
    )

    axis_line: Var[bool | dict[str, Any]] = field(
        doc="If false set, axis line will not be drawn. If true set, axis line will be drawn which have the props calculated internally. If object set, axis line will be drawn which have the props mergered by the internal calculated props and the option. Default: True"
    )

    axis_line_type: Var[LiteralGridType] = field(
        doc='The type of axis line. Default: "polygon"'
    )

    tick_line: Var[bool | dict[str, Any]] = field(
        default=LiteralVar.create(False),
        doc="If false set, tick lines will not be drawn. If true set, tick lines will be drawn which have the props calculated internally. If object set, tick lines will be drawn which have the props mergered by the internal calculated props and the option. Default: False",
    )

    tick: Var[bool | dict[str, Any]] = field(
        doc="If false set, ticks will not be drawn. If true set, ticks will be drawn which have the props calculated internally. If object set, ticks will be drawn which have the props mergered by the internal calculated props and the option. Default: True"
    )

    ticks: Var[Sequence[dict[str, Any]]] = field(
        doc="The array of every tick's value and angle."
    )

    orientation: Var[str] = field(doc='The orientation of axis text. Default: "outer"')

    stroke: Var[str | Color] = field(
        default=LiteralVar.create(Color("gray", 10)),
        doc='The stroke color of axis. Default: rx.color("gray", 10)',
    )

    allow_duplicated_category: Var[bool] = field(
        doc='Allow the axis has duplicated categorys or not when the type of axis is "category". Default: True'
    )

    # Valid children components.
    _valid_children: ClassVar[list[str]] = ["Label"]

    on_click: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of click on the ticks of this axis."
    )

    on_mouse_down: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mousedown on the the ticks of this axis."
    )

    on_mouse_up: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseup on the ticks of this axis."
    )

    on_mouse_move: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mousemove on the ticks of this axis."
    )

    on_mouse_over: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseover on the ticks of this axis."
    )

    on_mouse_out: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseout on the ticks of this axis."
    )

    on_mouse_enter: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of moustenter on the ticks of this axis."
    )

    on_mouse_leave: EventHandler[no_args_event_spec] = field(
        doc="The customized event handler of mouseleave on the ticks of this axis."
    )


class PolarGrid(Recharts):
    """A PolarGrid component in Recharts."""

    tag = "PolarGrid"

    alias = "RechartsPolarGrid"

    cx: Var[int] = field(doc="The x-coordinate of center.")

    cy: Var[int] = field(doc="The y-coordinate of center.")

    inner_radius: Var[int] = field(doc="The radius of the inner polar grid.")

    outer_radius: Var[int] = field(doc="The radius of the outer polar grid.")

    polar_angles: Var[Sequence[int]] = field(
        doc="The array of every line grid's angle."
    )

    polar_radius: Var[Sequence[int]] = field(
        doc="The array of every line grid's radius."
    )

    grid_type: Var[LiteralGridType] = field(
        doc="The type of polar grids. 'polygon' | 'circle'. Default: \"polygon\""
    )

    stroke: Var[str | Color] = field(
        default=LiteralVar.create(Color("gray", 10)),
        doc='The stroke color of grid. Default: rx.color("gray", 10)',
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = ["RadarChart", "RadiarBarChart"]


class PolarRadiusAxis(Recharts):
    """A PolarRadiusAxis component in Recharts."""

    tag = "PolarRadiusAxis"

    alias = "RechartsPolarRadiusAxis"

    angle: Var[int] = field(
        doc="The angle of radial direction line to display axis text. Default: 0"
    )

    type_: Var[LiteralPolarRadiusType] = field(
        doc="The type of axis line. 'number' | 'category'. Default: \"category\""
    )

    allow_duplicated_category: Var[bool] = field(
        doc='Allow the axis has duplicated categorys or not when the type of axis is "category". Default: True'
    )

    cx: Var[int] = field(doc="The x-coordinate of center.")

    cy: Var[int] = field(doc="The y-coordinate of center.")

    reversed: Var[bool] = field(
        doc="If set to true, the ticks of this axis are reversed. Default: False"
    )

    orientation: Var[LiteralOrientationLeftRightMiddle] = field(
        doc='The orientation of axis text. Default: "right"'
    )

    axis_line: Var[bool | dict[str, Any]] = field(
        doc="If false set, axis line will not be drawn. If true set, axis line will be drawn which have the props calculated internally. If object set, axis line will be drawn which have the props mergered by the internal calculated props and the option. Default: True"
    )

    tick: Var[bool | dict[str, Any]] = field(
        doc="If false set, ticks will not be drawn. If true set, ticks will be drawn which have the props calculated internally. If object set, ticks will be drawn which have the props mergered by the internal calculated props and the option. Default: True"
    )

    tick_count: Var[int] = field(
        doc="The count of axis ticks. Not used if 'type' is 'category'. Default: 5"
    )

    scale: Var[LiteralScale] = field(
        doc="If 'auto' set, the scale function is linear scale. 'auto' | 'linear' | 'pow' | 'sqrt' | 'log' | 'identity' | 'time' | 'band' | 'point' | 'ordinal' | 'quantile' | 'quantize' | 'utc' | 'sequential' | 'threshold'. Default: \"auto\""
    )

    # Valid children components
    _valid_children: ClassVar[list[str]] = ["Label"]

    domain: Var[Sequence[int | str]] = field(
        doc='The domain of the polar radius axis, specifying the minimum and maximum values. Default: [0, "auto"]'
    )

    stroke: Var[str | Color] = field(
        default=LiteralVar.create(Color("gray", 10)),
        doc='The stroke color of axis. Default: rx.color("gray", 10)',
    )

    @classmethod
    def get_event_triggers(cls) -> dict[str, Var | Any]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger to the var that is passed to the handler.
        """
        return {
            EventTriggers.ON_CLICK: no_args_event_spec,
            EventTriggers.ON_MOUSE_MOVE: no_args_event_spec,
            EventTriggers.ON_MOUSE_OVER: no_args_event_spec,
            EventTriggers.ON_MOUSE_OUT: no_args_event_spec,
            EventTriggers.ON_MOUSE_ENTER: no_args_event_spec,
            EventTriggers.ON_MOUSE_LEAVE: no_args_event_spec,
        }


pie = Pie.create
radar = Radar.create
radial_bar = RadialBar.create
polar_angle_axis = PolarAngleAxis.create
polar_grid = PolarGrid.create
polar_radius_axis = PolarRadiusAxis.create
