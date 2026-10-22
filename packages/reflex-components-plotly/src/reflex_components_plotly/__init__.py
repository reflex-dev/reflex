"""Plotly components."""

from reflex_base.components.component import ComponentNamespace

from .plotly import (
    Plotly,
    PlotlyBasic,
    PlotlyCartesian,
    PlotlyFinance,
    PlotlyGeo,
    PlotlyGl2d,
    PlotlyGl3d,
    PlotlyMap,
    PlotlyMapbox,
    PlotlyStrict,
)


class PlotlyNamespace(ComponentNamespace):
    """Plotly namespace."""

    __call__ = Plotly.create
    basic = PlotlyBasic.create
    cartesian = PlotlyCartesian.create
    geo = PlotlyGeo.create
    gl2d = PlotlyGl2d.create
    gl3d = PlotlyGl3d.create
    finance = PlotlyFinance.create
    map = PlotlyMap.create
    mapbox = PlotlyMapbox.create
    strict = PlotlyStrict.create


plotly = PlotlyNamespace()
