"""The charts page: recharts over a computed series and a plotly figure built as a dict."""

from typing import Any

import reflex as rx

from playground.layout import layout
from playground.states.charts import KINDS, MAX_POINTS, MIN_POINTS, ChartsState

CHART_SIZE = {"width": "100%", "height": 280}


def waves_chart() -> rx.Component | rx.Var:
    """Render the series as the chosen kind of recharts chart.

    Returns:
        A line, area or bar chart.
    """
    axes = (
        rx.recharts.x_axis(data_key="x"),
        rx.recharts.y_axis(),
        rx.recharts.cartesian_grid(stroke_dasharray="3 3"),
        rx.recharts.graphing_tooltip(),
        rx.recharts.legend(),
    )
    return rx.match(
        ChartsState.kind,
        (
            "area",
            rx.recharts.area_chart(
                rx.recharts.area(data_key="sine", fill=rx.color("accent", 6)),
                rx.recharts.area(data_key="cosine", fill=rx.color("gray", 6)),
                *axes,
                data=ChartsState.series,
                **CHART_SIZE,
            ),
        ),
        (
            "bar",
            rx.recharts.bar_chart(
                rx.recharts.bar(data_key="sine", fill=rx.color("accent", 9)),
                rx.recharts.bar(data_key="cosine", fill=rx.color("gray", 9)),
                *axes,
                data=ChartsState.series,
                **CHART_SIZE,
            ),
        ),
        rx.recharts.line_chart(
            rx.recharts.line(data_key="sine", stroke=rx.color("accent", 9)),
            rx.recharts.line(data_key="cosine", stroke=rx.color("gray", 9)),
            *axes,
            data=ChartsState.series,
            **CHART_SIZE,
        ),
    )


def charts() -> rx.Component:
    """Render the charts page.

    Returns:
        The controls, the recharts chart and the plotly figure.
    """
    return layout(
        rx.vstack(
            rx.heading("Charts"),
            rx.hstack(
                rx.select(
                    list(KINDS),
                    value=ChartsState.kind,
                    on_change=ChartsState.set_kind,
                    id="charts-kind",
                ),
                rx.button("Shift", on_click=ChartsState.shift, id="charts-shift"),
                rx.text("Points: ", ChartsState.points, id="charts-points"),
                align="center",
                spacing="3",
            ),
            rx.slider(
                default_value=[ChartsState.points],
                min=MIN_POINTS,
                max=MAX_POINTS,
                on_value_commit=ChartsState.set_points,
                id="charts-resolution",
            ),
            rx.box(waves_chart(), id="charts-recharts", width="100%"),
            rx.box(
                # A dict, not a plotly Figure: the app needs no plotly package.
                rx.plotly(data=ChartsState.figure.to(Any)),
                id="charts-plotly",
                width="100%",
            ),
            width="100%",
        )
    )
