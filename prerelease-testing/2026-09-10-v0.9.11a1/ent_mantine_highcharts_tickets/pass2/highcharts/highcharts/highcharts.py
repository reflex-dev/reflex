"""Highcharts (``@highcharts/react``) demos for Reflex Enterprise.

Shows the two ways to build a chart: composed from child components (with a
point-click handler driving state), and configured entirely from an options
dict. Highcharts requires a commercial license for commercial use.
"""

import reflex as rx

import reflex_enterprise as rxe

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]


class HighchartsState(rx.State):
    """State for the Highcharts demo."""

    last_point: str = "Click a point on the 2026 line to see it here."

    @rx.event
    def on_point_click(self, point: dict):
        """Record the clicked point.

        Args:
            point: The clicked point's plain fields (x, y, category, name, index).
        """
        self.last_point = f"Clicked {point['category']}: {point['y']} units"


def composed_chart() -> rx.Component:
    """A column + line chart composed from child components, with a click handler."""
    return rxe.highcharts(
        rxe.highcharts.title("Monthly sales"),
        rxe.highcharts.subtitle("Composed from child components"),
        rxe.highcharts.x_axis(categories=MONTHS),
        rxe.highcharts.y_axis(custom_attrs={"title": {"text": "Units"}}),
        rxe.highcharts.tooltip(shared=True),
        rxe.highcharts.legend(enabled=True),
        rxe.highcharts.column_series(name="2025", data=[3, 5, 1, 6, 4, 7]),
        rxe.highcharts.line_series(
            name="2026",
            data=[2, 4, 3, 5, 6, 8],
            events={"click": HighchartsState.on_point_click},
        ),
        rxe.highcharts.exporting(enabled=True, filename="monthly-sales"),
        container_props={"style": {"height": "420px"}},
    )


def options_chart() -> rx.Component:
    """The same surface driven entirely by an options dict (ag_chart-style)."""
    return rxe.highcharts(
        options={
            "chart": {"type": "pie"},
            "title": {"text": "Traffic sources"},
            "series": [
                {
                    "name": "Share",
                    "data": [
                        {"name": "Search", "y": 55},
                        {"name": "Direct", "y": 25},
                        {"name": "Social", "y": 20},
                    ],
                }
            ],
        },
        container_props={"style": {"height": "420px"}},
    )


def index() -> rx.Component:
    """The demo page."""
    return rx.container(
        rx.vstack(
            rx.hstack(
                rx.heading("Highcharts in Reflex Enterprise"),
                rx.spacer(),
                # Toggle the app color mode; the charts follow it via styled mode.
                rx.color_mode.button(),
                width="100%",
                align="center",
            ),
            rx.text(HighchartsState.last_point, weight="bold"),
            composed_chart(),
            options_chart(),
            spacing="4",
            width="100%",
            padding_y="2em",
        ),
        size="3",
    )


from . import state_demo  # noqa: E402, F401  # ADDED BY QA

app = rxe.App()
app.add_page(index, route="/", title="Highcharts demo")
