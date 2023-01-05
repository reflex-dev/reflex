"""Convenience functions to define layout components."""

from .plotly import Plotly
from .victory import Chart, Line, Scatter, Area, Bar, Pie, Polar, Candlestick, BoxPlot, Histogram, ErrorBar, Group, Stack, Voronoi
__all__ = [f for f in dir() if f[0].isupper()]  # type: ignore
