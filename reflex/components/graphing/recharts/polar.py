from typing import Any, Dict, List, Optional, Union

from reflex.components.component import Component
from reflex.style import Style
from reflex.vars import Var
from .recharts import Recharts


class Polar(Recharts):
    pass


class Pie(Recharts):

    tag = "Pie"

    # The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container width.
    cx: Var[Union[int, str]]

    # The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container height.
    cy: Var[Union[int, str]]

    # The inner radius of pie, which can be set to a percent value.
    inner_radius: Var[Union[int, str]]

    # The outer radius of pie, which can be set to a percent value.
    outer_radius: Var[Union[int, str]]

    # The angle of first sector.
    start_angle: Var[int]

    # The direction of sectors. 1 means clockwise and -1 means anticlockwise.
    end_angle: Var[int]

    # The minimum angle of each unzero data.
    min_angle: Var[int]

    # The angle between two sectors.
    padding_angle: Var[int]

    # The key of each sector's value.
    data_key: Var[str]

    # The key of each sector's name.
    name_key: Var[str]

    # The type of icon in legend. If set to 'none', no legend item will be rendered.
    legend_type: Var[str]

    # Specifies when the animation should begin, the unit of this option is ms.
    animation_begin: Var[int]

    # Specifies the duration of animation, the unit of this option is ms.
    animation_duration: Var[int]

    # The type of easing function. 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'linear'
    animation_easing: Var[str]


class Radar(Recharts):

    tag = "Radar"

    # The key of a group of data which should be unique in a radar chart.
    data_key: Var[str]

    # The coordinates of all the vertexes of the radar shape, like [{ x, y }].
    points: Var[List[Dict[str, Any]]]

    # The type of icon in legend. If set to 'none', no legend item will be rendered.
    legend_type: Var[str]

    # Specifies when the animation should begin, the unit of this option is ms.
    animation_begin: Var[int]

    # Specifies the duration of animation, the unit of this option is ms.
    animation_duration: Var[int]

    # The type of easing function. 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'linear'
    animation_easing: Var[str]


class RadialBar(Recharts):

    tag = "RadialBar"

    # The source data which each element is an object.
    data: Var[List[Dict[str, Any]]]


class PolarAngleAxis(Recharts):

    tag = "PolarAngleAxis"

    # The key of a group of data which should be unique to show the meaning of angle axis.
    data_key: Var[str]

    # The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container width.
    cx: Var[Union[int, str]]

    # The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container height.
    cy: Var[Union[int, str]]

    # The outer radius of circle grid. If set a percentage, the final value is obtained by multiplying the percentage of maxRadius which is calculated by the width, height, cx, cy.
    radius: Var[Union[int, str]]

    # If false set, axis line will not be drawn. If true set, axis line will be drawn which have the props calculated internally. If object set, axis line will be drawn which have the props mergered by the internal calculated props and the option.
    axis_line: Var[Union[bool, Dict[str, Any]]]

    # The type of axis line.
    axis_line_type: Var[str]

    # If false set, tick lines will not be drawn. If true set, tick lines will be drawn which have the props calculated internally. If object set, tick lines will be drawn which have the props mergered by the internal calculated props and the option.
    tick_line: Var[Union[bool, Dict[str, Any]]]

    # The width or height of tick.
    tick: Var[Union[int, str]]

    # The array of every tick's value and angle.
    ticks: Var[List[Dict[str, Any]]]


class PolarGrid(Recharts):

    tag = "PolarGrid"

    # The x-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container width.
    cx: Var[Union[int, str]]

    # The y-coordinate of center. If set a percentage, the final value is obtained by multiplying the percentage of container height.
    cy: Var[Union[int, str]]

    # The radius of the inner polar grid.
    inner_radius: Var[Union[int, str]]

    # The radius of the outer polar grid.
    outer_radius: Var[Union[int, str]]

    # The array of every line grid's angle.
    polar_angles: Var[List[int]]

    # The array of every line grid's radius.
    polar_radius: Var[List[int]]

    # The type of polar grids. 'polygon' | 'circle'
    grid_type: Var[str]


class PolarRadiusAxis(Recharts):

    tag = "PolarRadiusAxis"

    # The angle of radial direction line to display axis text.
    angle: Var[int]

    # The type of axis line. 'number' | 'category'
    _type: Var[str]

    # Allow the axis has duplicated categorys or not when the type of axis is "category".
    allow_duplicated_category: Var[bool]

    # The x-coordinate of center.
    cx: Var[Union[int, str]]

    # The y-coordinate of center.
    cy: Var[Union[int, str]]

    # If set to true, the ticks of this axis are reversed.
    reversed: Var[bool]

    # The orientation of axis text.
    orientation: Var[str]

    # If false set, axis line will not be drawn. If true set, axis line will be drawn which have the props calculated internally. If object set, axis line will be drawn which have the props mergered by the internal calculated props and the option.
    axis_line: Var[Union[bool, Dict[str, Any]]]

    # The width or height of tick.
    tick: Var[Union[int, str]]

    # The count of ticks.
    tick_count: Var[int]
