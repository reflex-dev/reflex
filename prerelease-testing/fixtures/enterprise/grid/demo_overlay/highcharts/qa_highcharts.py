"""QA page for the highcharts demo (our own; fetch_demos.sh imports it from the demo's main module).

Series data and an options dict built from State vars; drive_highcharts.py checks they follow State and survive reload.
"""

import reflex_enterprise as rxe

import reflex as rx


class QaHighchartsState(rx.State):
    """State-driven series and options for QA."""

    data: list[int] = [1, 2, 3]
    pie: list[dict] = [{"name": "A", "y": 60}, {"name": "B", "y": 40}]
    title: str = "QA dynamic"

    @rx.event
    def push(self):
        """Append one point."""
        self.data = [*self.data, len(self.data) + 1]

    @rx.event
    def retitle(self):
        """Change the title and the pie data."""
        self.title = "QA retitled"
        self.pie = [{"name": "A", "y": 10}, {"name": "B", "y": 30}, {"name": "C", "y": 60}]


@rx.page(route="/qa", title="Highcharts QA")
def qa_page() -> rx.Component:
    """QA page: series data / options from State.

    Returns:
        The QA page.
    """
    return rx.vstack(
        rx.button("push point", on_click=QaHighchartsState.push, id="qa-push"),
        rx.button("retitle", on_click=QaHighchartsState.retitle, id="qa-retitle"),
        rxe.highcharts(
            rxe.highcharts.title(QaHighchartsState.title),
            rxe.highcharts.line_series(name="dyn", data=QaHighchartsState.data),
            container_props={"style": {"height": "300px"}, "id": "qa-line"},
        ),
        rxe.highcharts(
            options={
                "chart": {"type": "pie"},
                "title": {"text": QaHighchartsState.title},
                "series": [{"name": "s", "data": QaHighchartsState.pie}],
            },
            container_props={"style": {"height": "300px"}, "id": "qa-pie"},
        ),
    )
