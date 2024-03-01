"""Polar charts in Recharts."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from reflex.constants import EventTriggers
from reflex.vars import Var

from .recharts import (
    LiteralAnimationEasing,
    LiteralGridType,
    LiteralPolarRadiusType,
    LiteralScale,
    Recharts,
)


class Pie(Recharts):
    """A Pie chart component in Recharts."""

    tag: str = "Pie"

    alias: str = "RechartsPie"

    # data
    data: Optional[Var[List[Dict[str, Any]]]] = None

    # The key of each sector's value.
    data_key: Optional[Var[Union[str, int]]] = None

    # The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container width.
    cx: Optional[Var[Union[int, str]]] = None

    # The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container height.
    cy: Optional[Var[Union[int, str]]] = None

    # The inner radius of pie, which can be set to a percent value.
    inner_radius: Optional[Var[Union[int, str]]] = None

    # The outer radius of pie, which can be set to a percent value.
    outer_radius: Optional[Var[Union[int, str]]] = None

    # The angle of first sector.
    start_angle: Optional[Var[int]] = None

    # The direction of sectors. 1 means clockwise and -1 means anticlockwise.
    end_angle: Optional[Var[int]] = None

    # The minimum angle of each unzero data.
    min_angle: Optional[Var[int]] = None

    # The angle between two sectors.
    padding_angle: Optional[Var[int]] = None

    # The key of each sector's name.
    name_key: Optional[Var[str]] = None

    # The type of icon in legend. If set to 'none', no legend item will be rendered.
    legend_type: Optional[Var[str]] = None

    # If false set, labels will not be drawn.
    label: Var[bool] = False  # type: ignore

    # If false set, label lines will not be drawn.
    label_line: Optional[Var[bool]] = None

    # Valid children components
    _valid_children: List[str] = ["Cell", "LabelList"]

    # fill color
    fill: Optional[Var[str]] = None

    # stroke color
    stroke: Optional[Var[str]] = None

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


class Radar(Recharts):
    """A Radar chart component in Recharts."""

    tag: str = "Radar"

    alias: str = "RechartsRadar"

    # The key of a group of data which should be unique in a radar chart.
    data_key: Optional[Var[Union[str, int]]] = None

    # The coordinates of all the vertexes of the radar shape, like [{ x, y }].
    points: Optional[Var[List[Dict[str, Any]]]] = None

    # If false set, dots will not be drawn
    dot: Optional[Var[bool]] = None

    # Stoke color
    stroke: Optional[Var[str]] = None

    # Fill color
    fill: Optional[Var[str]] = None

    # opacity
    fill_opacity: Optional[Var[float]] = None

    # The type of icon in legend. If set to 'none', no legend item will be rendered.
    legend_type: Optional[Var[str]] = None

    # If false set, labels will not be drawn
    label: Optional[Var[bool]] = None

    # Specifies when the animation should begin, the unit of this option is ms.
    animation_begin: Optional[Var[int]] = None

    # Specifies the duration of animation, the unit of this option is ms.
    animation_duration: Optional[Var[int]] = None

    # The type of easing function. 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'linear'
    animation_easing: Optional[Var[LiteralAnimationEasing]] = None

    # Valid children components
    _valid_children: List[str] = ["LabelList"]


class RadialBar(Recharts):
    """A RadialBar chart component in Recharts."""

    tag: str = "RadialBar"

    alias: str = "RechartsRadialBar"

    # The source data which each element is an object.
    data: Optional[Var[List[Dict[str, Any]]]] = None

    # Min angle of each bar. A positive value between 0 and 360.
    min_angle: Optional[Var[int]] = None

    # Type of legend
    legend_type: Optional[Var[str]] = None

    # If false set, labels will not be drawn.
    label: Optional[Var[bool]] = None

    # If false set, background sector will not be drawn.
    background: Optional[Var[bool]] = None

    # Valid children components
    _valid_children: List[str] = ["LabelList"]

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


class PolarAngleAxis(Recharts):
    """A PolarAngleAxis component in Recharts."""

    tag: str = "PolarAngleAxis"

    alias: str = "RechartsPolarAngleAxis"

    # The key of a group of data which should be unique to show the meaning of angle axis.
    data_key: Optional[Var[Union[str, int]]] = None

    # The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container width.
    cx: Optional[Var[Union[int, str]]] = None

    # The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container height.
    cy: Optional[Var[Union[int, str]]] = None

    # The outer radius of circle grid. If set a percentage, the final value is obtained by multiplying the percentage of maxRadius which is calculated by the width, height, cx, cy.
    radius: Optional[Var[Union[int, str]]] = None

    # If false set, axis line will not be drawn. If true set, axis line will be drawn which have the props calculated internally. If object set, axis line will be drawn which have the props mergered by the internal calculated props and the option.
    axis_line: Optional[Var[Union[bool, Dict[str, Any]]]] = None

    # The type of axis line.
    axis_line_type: Optional[Var[str]] = None

    # If false set, tick lines will not be drawn. If true set, tick lines will be drawn which have the props calculated internally. If object set, tick lines will be drawn which have the props mergered by the internal calculated props and the option.
    tick_line: Optional[Var[Union[bool, Dict[str, Any]]]] = None

    # The width or height of tick.
    tick: Optional[Var[Union[int, str]]] = None

    # The array of every tick's value and angle.
    ticks: Optional[Var[List[Dict[str, Any]]]] = None

    # The orientation of axis text.
    orient: Optional[Var[str]] = None

    # Allow the axis has duplicated categorys or not when the type of axis is "category".
    allow_duplicated_category: Optional[Var[bool]] = None

    # Valid children components
    _valid_children: List[str] = ["Label"]

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


class PolarGrid(Recharts):
    """A PolarGrid component in Recharts."""

    tag: str = "PolarGrid"

    alias: str = "RechartsPolarGrid"

    # The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container width.
    cx: Optional[Var[Union[int, str]]] = None

    # The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container height.
    cy: Optional[Var[Union[int, str]]] = None

    # The radius of the inner polar grid.
    inner_radius: Optional[Var[Union[int, str]]] = None

    # The radius of the outer polar grid.
    outer_radius: Optional[Var[Union[int, str]]] = None

    # The array of every line grid's angle.
    polar_angles: Optional[Var[List[int]]] = None

    # The array of every line grid's radius.
    polar_radius: Optional[Var[List[int]]] = None

    # The type of polar grids. 'polygon' | 'circle'
    grid_type: Optional[Var[LiteralGridType]] = None

    # Valid children components
    _valid_children: List[str] = ["RadarChart", "RadiarBarChart"]


class PolarRadiusAxis(Recharts):
    """A PolarRadiusAxis component in Recharts."""

    tag: str = "PolarRadiusAxis"

    alias: str = "RechartsPolarRadiusAxis"

    # The angle of radial direction line to display axis text.
    angle: Optional[Var[int]] = None

    # The type of axis line. 'number' | 'category'
    type_: Optional[Var[LiteralPolarRadiusType]] = None

    # Allow the axis has duplicated categorys or not when the type of axis is "category".
    allow_duplicated_category: Optional[Var[bool]] = None

    # The x-coordinate of center.
    cx: Optional[Var[Union[int, str]]] = None

    # The y-coordinate of center.
    cy: Optional[Var[Union[int, str]]] = None

    # If set to true, the ticks of this axis are reversed.
    reversed: Optional[Var[bool]] = None

    # The orientation of axis text.
    orientation: Optional[Var[str]] = None

    # If false set, axis line will not be drawn. If true set, axis line will be drawn which have the props calculated internally. If object set, axis line will be drawn which have the props mergered by the internal calculated props and the option.
    axis_line: Optional[Var[Union[bool, Dict[str, Any]]]] = None

    # The width or height of tick.
    tick: Optional[Var[Union[int, str]]] = None

    # The count of ticks.
    tick_count: Optional[Var[int]] = None

    # If 'auto' set, the scale funtion is linear scale. 'auto' | 'linear' | 'pow' | 'sqrt' | 'log' | 'identity' | 'time' | 'band' | 'point' | 'ordinal' | 'quantile' | 'quantize' | 'utc' | 'sequential' | 'threshold'
    scale: Optional[Var[LiteralScale]] = None

    # Valid children components
    _valid_children: List[str] = ["Label"]

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
