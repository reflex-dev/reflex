"""Plotly components."""

from reflex_base.components.component import ComponentNamespace

from .plotly import Plotly as Plotly
from .plotly import PlotlyBasic as PlotlyBasic
from .plotly import PlotlyCartesian as PlotlyCartesian
from .plotly import PlotlyFinance as PlotlyFinance
from .plotly import PlotlyGeo as PlotlyGeo
from .plotly import PlotlyGl2d as PlotlyGl2d
from .plotly import PlotlyGl3d as PlotlyGl3d
from .plotly import PlotlyMapbox as PlotlyMapbox
from .plotly import PlotlyStrict as PlotlyStrict


class PlotlyNamespace(ComponentNamespace):
    """Plotly namespace."""

    __call__ = Plotly.create
    basic = PlotlyBasic.create
    cartesian = PlotlyCartesian.create
    geo = PlotlyGeo.create
    gl2d = PlotlyGl2d.create
    gl3d = PlotlyGl3d.create
    finance = PlotlyFinance.create
    mapbox = PlotlyMapbox.create
    strict = PlotlyStrict.create


plotly = PlotlyNamespace()
