"""Polar charts in Recharts."""

from __future__ import annotations

from typing import Any, Dict, List, Union

from reflex.constants import EventTriggers
from reflex.constants.colors import Color
from reflex.event import EventHandler, no_args_event_spec
from reflex.vars.base import LiteralVar, Var

from .recharts import (
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

    # The source data which each element is an object.
    data: Var[List[Dict[str, Any]]]

    # The key of each sector's value.
    data_key: Var[Union[str, int]]

    # The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container width. Default: "50%"
    cx: Var[Union[int, str]]

    # The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container height. Default: "50%"
    cy: Var[Union[int, str]]

    # The inner radius of pie, which can be set to a percent value. Default: 0
    inner_radius: Var[Union[int, str]]

    # The outer radius of pie, which can be set to a percent value. Default: "80%"
    outer_radius: Var[Union[int, str]]

    # The angle of first sector. Default: 0
    start_angle: Var[int]

    # The end angle of last sector, which should be unequal to start_angle. Default: 360
    end_angle: Var[int]

    # The minimum angle of each unzero data. Default: 0
    min_angle: Var[int]

    # The angle between two sectors. Default: 0
    padding_angle: Var[int]

    # The key of each sector's name. Default: "name"
    name_key: Var[str]

    # The type of icon in legend. If set to 'none', no legend item will be rendered. Default: "rect"
    legend_type: Var[LiteralLegendType]

    # If false set, labels will not be drawn. If true set, labels will be drawn which have the props calculated internally. Default: False
    label: Var[bool] = False  # type: ignore

    # If false set, label lines will not be drawn. If true set, label lines will be drawn which have the props calculated internally. Default: False
    label_line: Var[bool]

    # The index of active sector in Pie, this option can be changed in mouse event handlers.
    data: Var[List[Dict[str, Any]]]

    # Valid children components
    _valid_children: List[str] = ["Cell", "LabelList"]

    # Stoke color. Default: rx.color("accent", 9)
    stroke: Var[Union[str, Color]] = LiteralVar.create(Color("accent", 9))

    # Fill color. Default: rx.color("accent", 3)
    fill: Var[Union[str, Color]] = LiteralVar.create(Color("accent", 3))

    # If set false, animation of tooltip will be disabled. Default: true in CSR, and false in SSR
    is_animation_active: Var[bool]

    # Specifies when the animation should begin, the unit of this option is ms. Default: 400
    animation_begin: Var[int]

    # Specifies the duration of animation, the unit of this option is ms. Default: 1500
    animation_duration: Var[int]

    # The type of easing function. Default: "ease"
    animation_easing: Var[LiteralAnimationEasing]

    # The tabindex of wrapper surrounding the cells. Default: 0
    root_tab_index: Var[int]

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
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

    # The key of a group of data which should be unique in a radar chart.
    data_key: Var[Union[str, int]]

    # The coordinates of all the vertexes of the radar shape, like [{ x, y }].
    points: Var[List[Dict[str, Any]]]

    # If false set, dots will not be drawn. Default: True
    dot: Var[bool]

    # Stoke color. Default: rx.color("accent", 9)
    stroke: Var[Union[str, Color]] = LiteralVar.create(Color("accent", 9))

    # Fill color. Default: rx.color("accent", 3)
    fill: Var[str] = LiteralVar.create(Color("accent", 3))

    # The opacity to fill the chart. Default: 0.6
    fill_opacity: Var[float] = LiteralVar.create(0.6)

    # The type of icon in legend. If set to 'none', no legend item will be rendered. Default: "rect"
    legend_type: Var[LiteralLegendType]

    # If false set, labels will not be drawn. Default: True
    label: Var[bool]

    # If set false, animation of polygon will be disabled. Default: True in CSR, and False in SSR
    is_animation_active: Var[bool]

    # Specifies when the animation should begin, the unit of this option is ms. Default: 0
    animation_begin: Var[int]

    # Specifies the duration of animation, the unit of this option is ms. Default: 1500
    animation_duration: Var[int]

    # The type of easing function. 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'linear'. Default: "ease"
    animation_easing: Var[LiteralAnimationEasing]

    # Valid children components
    _valid_children: List[str] = ["LabelList"]

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
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

    # The source data which each element is an object.
    data: Var[List[Dict[str, Any]]]

    # The key of a group of data which should be unique to show the meaning of angle axis.
    data_key: Var[Union[str, int]]

    # Min angle of each bar. A positive value between 0 and 360. Default: 0
    min_angle: Var[int]

    # The type of icon in legend. If set to 'none', no legend item will be rendered. Default: "rect"
    legend_type: Var[LiteralLegendType]

    # If false set, labels will not be drawn. If true set, labels will be drawn which have the props calculated internally. Default: False
    label: Var[Union[bool, Dict[str, Any]]]

    # If false set, background sector will not be drawn. Default: False
    background: Var[Union[bool, Dict[str, Any]]]

    # If set false, animation of radial bars will be disabled. Default: True
    is_animation_active: Var[bool]

    # Specifies when the animation should begin, the unit of this option is ms. Default: 0
    animation_begin: Var[int]

    # Specifies the duration of animation, the unit of this option is ms. Default 1500
    animation_duration: Var[int]

    # The type of easing function. 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'linear'. Default: "ease"
    animation_easing: Var[LiteralAnimationEasing]

    # Valid children components
    _valid_children: List[str] = ["Cell", "LabelList"]

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
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

    # The key of a group of data which should be unique to show the meaning of angle axis.
    data_key: Var[Union[str, int]]

    # The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container width.
    cx: Var[Union[int, str]]

    # The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container height.
    cy: Var[Union[int, str]]

    # The outer radius of circle grid. If set a percentage, the final value is obtained by multiplying the percentage of maxRadius which is calculated by the width, height, cx, cy.
    radius: Var[Union[int, str]]

    # If false set, axis line will not be drawn. If true set, axis line will be drawn which have the props calculated internally. If object set, axis line will be drawn which have the props mergered by the internal calculated props and the option. Default: True
    axis_line: Var[Union[bool, Dict[str, Any]]]

    # The type of axis line. Default: "polygon"
    axis_line_type: Var[LiteralGridType]

    # If false set, tick lines will not be drawn. If true set, tick lines will be drawn which have the props calculated internally. If object set, tick lines will be drawn which have the props mergered by the internal calculated props and the option. Default: False
    tick_line: Var[Union[bool, Dict[str, Any]]] = LiteralVar.create(False)

    # If false set, ticks will not be drawn. If true set, ticks will be drawn which have the props calculated internally. If object set, ticks will be drawn which have the props mergered by the internal calculated props and the option. Default: True
    tick: Var[Union[bool, Dict[str, Any]]]

    # The array of every tick's value and angle.
    ticks: Var[List[Dict[str, Any]]]

    # The orientation of axis text. Default: "outer"
    orientation: Var[str]

    # The stroke color of axis. Default: rx.color("gray", 10)
    stroke: Var[Union[str, Color]] = LiteralVar.create(Color("gray", 10))

    # Allow the axis has duplicated categorys or not when the type of axis is "category". Default: True
    allow_duplicated_category: Var[bool]

    # Valid children components.
    _valid_children: List[str] = ["Label"]

    # The customized event handler of click on the ticks of this axis.
    on_click: EventHandler[no_args_event_spec]

    # The customized event handler of mousedown on the the ticks of this axis.
    on_mouse_down: EventHandler[no_args_event_spec]

    # The customized event handler of mouseup on the ticks of this axis.
    on_mouse_up: EventHandler[no_args_event_spec]

    # The customized event handler of mousemove on the ticks of this axis.
    on_mouse_move: EventHandler[no_args_event_spec]

    # The customized event handler of mouseover on the ticks of this axis.
    on_mouse_over: EventHandler[no_args_event_spec]

    # The customized event handler of mouseout on the ticks of this axis.
    on_mouse_out: EventHandler[no_args_event_spec]

    # The customized event handler of moustenter on the ticks of this axis.
    on_mouse_enter: EventHandler[no_args_event_spec]

    # The customized event handler of mouseleave on the ticks of this axis.
    on_mouse_leave: EventHandler[no_args_event_spec]


class PolarGrid(Recharts):
    """A PolarGrid component in Recharts."""

    tag = "PolarGrid"

    alias = "RechartsPolarGrid"

    # The x-coordinate of center.
    cx: Var[int]

    # The y-coordinate of center.
    cy: Var[int]

    # The radius of the inner polar grid.
    inner_radius: Var[int]

    # The radius of the outer polar grid.
    outer_radius: Var[int]

    # The array of every line grid's angle.
    polar_angles: Var[List[int]]

    # The array of every line grid's radius.
    polar_radius: Var[List[int]]

    # The type of polar grids. 'polygon' | 'circle'. Default: "polygon"
    grid_type: Var[LiteralGridType]

    # The stroke color of grid. Default: rx.color("gray", 10)
    stroke: Var[Union[str, Color]] = LiteralVar.create(Color("gray", 10))

    # Valid children components
    _valid_children: List[str] = ["RadarChart", "RadiarBarChart"]


class PolarRadiusAxis(Recharts):
    """A PolarRadiusAxis component in Recharts."""

    tag = "PolarRadiusAxis"

    alias = "RechartsPolarRadiusAxis"

    # The angle of radial direction line to display axis text. Default: 0
    angle: Var[int]

    # The type of axis line. 'number' | 'category'. Default: "category"
    type_: Var[LiteralPolarRadiusType]

    # Allow the axis has duplicated categorys or not when the type of axis is "category". Default: True
    allow_duplicated_category: Var[bool]

    # The x-coordinate of center.
    cx: Var[int]

    # The y-coordinate of center.
    cy: Var[int]

    # If set to true, the ticks of this axis are reversed. Default: False
    reversed: Var[bool]

    # The orientation of axis text. Default: "right"
    orientation: Var[LiteralOrientationLeftRightMiddle]

    # If false set, axis line will not be drawn. If true set, axis line will be drawn which have the props calculated internally. If object set, axis line will be drawn which have the props mergered by the internal calculated props and the option. Default: True
    axis_line: Var[Union[bool, Dict[str, Any]]]

    # If false set, ticks will not be drawn. If true set, ticks will be drawn which have the props calculated internally. If object set, ticks will be drawn which have the props mergered by the internal calculated props and the option. Default: True
    tick: Var[Union[bool, Dict[str, Any]]]

    # The count of axis ticks. Not used if 'type' is 'category'. Default: 5
    tick_count: Var[int]

    # If 'auto' set, the scale funtion is linear scale. 'auto' | 'linear' | 'pow' | 'sqrt' | 'log' | 'identity' | 'time' | 'band' | 'point' | 'ordinal' | 'quantile' | 'quantize' | 'utc' | 'sequential' | 'threshold'. Default: "auto"
    scale: Var[LiteralScale]

    # Valid children components
    _valid_children: List[str] = ["Label"]

    # The domain of the polar radius axis, specifying the minimum and maximum values. Default: [0, "auto"]
    domain: Var[List[Union[int, str]]]

    # The stroke color of axis. Default: rx.color("gray", 10)
    stroke: Var[Union[str, Color]] = LiteralVar.create(Color("gray", 10))

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
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
