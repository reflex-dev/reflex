"""Optional chart route, kept in its own source module."""

import plotly.graph_objects as go
import reflex as rx
from .common import shell


class ReportsState(rx.State):
    """Small chart source data; heavy cost should be JavaScript library code."""

    points: list[int] = [12, 18, 14, 22, 25, 31]
    updates: int = 0

    @rx.var
    def figure(self) -> go.Figure:
        """Build the sales trend figure.

        Returns:
            A simple Plotly figure.
        """
        return go.Figure(
            data=[go.Scatter(x=list(range(1, len(self.points) + 1)), y=self.points)],
            layout={"title": {"text": "Weekly sales"}, "height": 340},
        )

    @rx.event
    def add_week(self):
        """Append one sales observation."""
        self.points.append(self.points[-1] + 3)
        self.updates += 1


def reports() -> rx.Component:
    """Build the chart route.

    Returns:
        Plotly chart and update control.
    """
    return shell(
        "Revenue reports",
        rx.button("Add week", id="add-week", on_click=ReportsState.add_week),
        rx.text(ReportsState.updates, id="chart-updates"),
        rx.plotly(data=ReportsState.figure, width="100%", id="sales-plot"),
    )
