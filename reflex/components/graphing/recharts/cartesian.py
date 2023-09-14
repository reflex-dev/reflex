from typing import Any, Dict, List, Optional, Union

from reflex.components.component import Component
from reflex.style import Style
from reflex.vars import Var
from .recharts import Recharts


class Cartesian(Recharts):

    # The layout of bar in the chart, usually inherited from parent. 'horizontal' | 'vertical'
    layout: Var[str]

    # The key of a group of data which should be unique in an area chart.
    data_key: Var[str]

    # The id of x-axis which is corresponding to the data.
    x_axis_id: Var[str]

    # The id of y-axis which is corresponding to the data.
    y_axis_id: Var[str]

    # The type of icon in legend. If set to 'none', no legend item will be rendered. 'line' | 'plainline' | 'square' | 'rect'| 'circle' | 'cross' | 'diamond' | 'square' | 'star' | 'triangle' | 'wye' | 'none'optional
    legend_type: Var[str]

class XAxis(Cartesian):

    tag = "XAxis"
    
    # The key of data displayed in the axis.
    data_key: Var[str]

class YAxis(Cartesian):

    tag = "YAxis"

    # The key of data displayed in the axis.
    data_key: Var[str]

class ZAxis(Cartesian):

    tag = "ZAxis"

    # The key of data displayed in the axis.
    data_key: Var[str]

class Area(Cartesian):

    tag = "Area"

    stroke: Var[str]

    fill: Var[str]

class Line(Cartesian):

    tag = "Line"

    stroke: Var[str]

    stoke_width: Var[int]