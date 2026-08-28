"""Minimal repro: does the id prop on rx.plotly reach the DOM?"""

import plotly.graph_objects as go

import reflex as rx


def _make_figure() -> go.Figure:
    """Build a small bar figure.

    Returns:
        The plotly figure.
    """
    fig = go.Figure(data=[go.Bar(x=["a", "b", "c"], y=[1, 3, 2])])
    fig.update_layout(title="repro chart")
    return fig


class State(rx.State):
    """State holding a plotly figure var."""

    figure: go.Figure = _make_figure()


STATIC_FIGURE = _make_figure()


def index() -> rx.Component:
    """Index page.

    Returns:
        The page component.
    """
    return rx.box(
        rx.box("control", id="control-box"),
        rx.plotly(data=State.figure, id="the-plot"),
        rx.plotly(data=STATIC_FIGURE, id="static-plot"),
        rx.plotly(data=STATIC_FIGURE, custom_attrs={"divId": "workaround-plot"}),
        id="page-root",
    )


app = rx.App()
app.add_page(index)
