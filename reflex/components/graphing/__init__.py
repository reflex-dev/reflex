"""Convenience functions to define layout components."""

from .plotly import Plotly
from .victory import (
    Area,
    Bar,
    BoxPlot,
    Candlestick,
    Chart,
    ChartGroup,
    ChartStack,
    ErrorBar,
    Histogram,
    Line,
    Pie,
    Polar,
    Scatter,
    Voronoi,
)
from .altair import Altair
from .bokeh import Bokeh
from .matplotlib import Pyplot

__all__ = [f for f in dir() if f[0].isupper()]  # type: ignore
