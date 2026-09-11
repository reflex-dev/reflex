"""ADDED BY PRE-RELEASE QA (not part of the shipped reflex-enterprise demo).

The shipped highcharts demo charts static python lists. This page charts *state*
data instead — series data, series name and a whole options dict driven by state
vars, updated from a plain event handler, an event chain and a background task —
which is how a real app uses a chart.

Routes:
    /state          state-driven series + options dict + background streaming
    /state-foreach  rx.foreach building series components (only with HC_FOREACH=1)
"""

import asyncio
import os

import reflex as rx

import reflex_enterprise as rxe


class SeriesState(rx.State):
    """State behind the state-driven charts."""

    values: list[int] = [2, 4, 3]
    label: str = "live"
    clicked: str = "none"
    streaming: bool = False

    @rx.var
    def options(self) -> dict:
        """A whole Highcharts options dict computed from state.

        Returns:
            The options for the options-driven chart.
        """
        return {
            "chart": {"type": "bar"},
            "title": {"text": f"options from state ({len(self.values)} points)"},
            "series": [{"name": self.label, "data": self.values}],
        }

    @rx.var
    def total(self) -> int:
        """The sum of the plotted values.

        Returns:
            Sum of ``values``.
        """
        return sum(self.values)

    @rx.event
    def add_point(self):
        """Append one point to the series."""
        self.values = [*self.values, (self.values[-1] * 7 + 3) % 11 + 1]

    @rx.event
    def rename(self):
        """Rename the series, then add a point through an event chain.

        Returns:
            The chained event.
        """
        self.label = f"live-{len(self.values)}"
        return SeriesState.add_point

    @rx.event
    def reset_series(self):
        """Restore the initial series."""
        self.values = [2, 4, 3]
        self.label = "live"
        self.clicked = "none"

    @rx.event
    def on_point(self, point: dict):
        """Record a click through the reflex-style ``on_click`` trigger.

        Args:
            point: The clicked point's plain fields.
        """
        self.clicked = f"{point['index']}={point['y']}"

    @rx.event(background=True)
    async def stream(self):
        """Append three points from a background task."""
        async with self:
            self.streaming = True
        for _ in range(3):
            await asyncio.sleep(0.6)
            async with self:
                self.values = [*self.values, (self.values[-1] * 5 + 1) % 9 + 1]
        async with self:
            self.streaming = False


def index_state() -> rx.Component:
    """The state-driven chart page.

    Returns:
        The page component.
    """
    return rx.container(
        rx.vstack(
            rx.heading("State-driven Highcharts"),
            rx.hstack(
                rx.button("Add point", on_click=SeriesState.add_point),
                rx.button("Rename + add (chain)", on_click=SeriesState.rename),
                rx.button("Stream (background)", on_click=SeriesState.stream),
                rx.button("Reset", on_click=SeriesState.reset_series),
                rx.color_mode.button(),
            ),
            rx.text("points: ", SeriesState.values.length(), id="npoints"),
            rx.text("total: ", SeriesState.total, id="total"),
            rx.text("clicked: ", SeriesState.clicked, id="clicked"),
            rx.text("streaming: ", SeriesState.streaming.to_string(), id="streaming"),
            rxe.highcharts(
                rxe.highcharts.title("series data from state"),
                rxe.highcharts.line_series(
                    name=SeriesState.label,
                    data=SeriesState.values,
                    on_click=SeriesState.on_point,
                ),
                container_props={"style": {"height": "320px"}},
            ),
            rxe.highcharts(
                options=SeriesState.options,
                container_props={"style": {"height": "320px"}},
            ),
            rx.cond(
                SeriesState.total > 9,
                rx.badge("total above 9", color_scheme="green", id="badge"),
                rx.badge("total 9 or below", color_scheme="red", id="badge"),
            ),
            spacing="3",
            width="100%",
            padding_y="2em",
        ),
        size="3",
    )


page = rx.page(route="/state", title="State-driven chart")(index_state)

if os.environ.get("HC_FOREACH"):

    class ForeachState(rx.State):
        """State for the foreach-built series."""

        series: list[dict] = [
            {"name": "a", "data": [1, 2, 3]},
            {"name": "b", "data": [3, 2, 1]},
        ]

    def index_foreach() -> rx.Component:
        """A chart whose series components come out of rx.foreach.

        Returns:
            The page component.
        """
        return rx.container(
            rx.heading("foreach series"),
            rxe.highcharts(
                rxe.highcharts.title("foreach"),
                rx.foreach(
                    ForeachState.series,
                    lambda s: rxe.highcharts.line_series(name=s["name"], data=s["data"]),
                ),
                container_props={"style": {"height": "320px"}},
            ),
        )

    foreach_page = rx.page(route="/state-foreach", title="Foreach series")(index_foreach)
