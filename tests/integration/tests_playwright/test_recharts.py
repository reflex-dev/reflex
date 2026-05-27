"""Integration tests for recharts graphing components."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def RechartsApp():
    """App exercising several recharts chart types, static and stateful."""
    import reflex as rx

    data = [
        {"name": "Page A", "uv": 4000, "pv": 2400},
        {"name": "Page B", "uv": 3000, "pv": 1398},
        {"name": "Page C", "uv": 2000, "pv": 9800},
        {"name": "Page D", "uv": 2780, "pv": 3908},
    ]

    pie_data = [
        {"name": "Group A", "value": 400},
        {"name": "Group B", "value": 300},
        {"name": "Group C", "value": 300},
    ]

    months = [
        {"name": "Jan", "uv": 100, "pv": 200},
        {"name": "Feb", "uv": 150, "pv": 250},
        {"name": "Mar", "uv": 120, "pv": 220},
    ]
    quarters = [
        {"name": "Q1", "uv": 500, "pv": 600},
        {"name": "Q2", "uv": 700, "pv": 800},
    ]

    class ChartState(rx.State):
        data: list[dict] = months
        toggled: bool = False

        @rx.event
        def toggle_data(self):
            self.toggled = not self.toggled
            self.data = quarters if self.toggled else months

    app = rx.App()

    @app.add_page
    def index():
        return rx.vstack(
            rx.box(
                rx.recharts.line_chart(
                    rx.recharts.line(data_key="pv", stroke="#8884d8"),
                    rx.recharts.line(data_key="uv", stroke="#82ca9d"),
                    rx.recharts.x_axis(data_key="name"),
                    rx.recharts.y_axis(),
                    data=data,
                    width="100%",
                    height=300,
                ),
                id="line_chart",
                width="600px",
                height="300px",
            ),
            rx.box(
                rx.recharts.bar_chart(
                    rx.recharts.bar(data_key="uv", fill="#8884d8"),
                    rx.recharts.x_axis(data_key="name"),
                    rx.recharts.y_axis(),
                    data=data,
                    width="100%",
                    height=300,
                ),
                id="bar_chart",
                width="600px",
                height="300px",
            ),
            rx.box(
                rx.recharts.area_chart(
                    rx.recharts.area(data_key="uv", stroke="#8884d8", fill="#8884d8"),
                    rx.recharts.x_axis(data_key="name"),
                    rx.recharts.y_axis(),
                    data=data,
                    width="100%",
                    height=300,
                ),
                id="area_chart",
                width="600px",
                height="300px",
            ),
            rx.box(
                rx.recharts.pie_chart(
                    rx.recharts.pie(
                        data=pie_data,
                        data_key="value",
                        name_key="name",
                        fill="#8884d8",
                    ),
                    width="100%",
                    height=300,
                ),
                id="pie_chart",
                width="600px",
                height="300px",
            ),
            rx.box(
                rx.recharts.bar_chart(
                    rx.recharts.bar(data_key="uv", fill="#8884d8"),
                    rx.recharts.x_axis(data_key="name"),
                    rx.recharts.y_axis(),
                    data=ChartState.data,
                    width="100%",
                    height=300,
                ),
                id="stateful_chart",
                width="600px",
                height="300px",
            ),
            rx.button("toggle", on_click=ChartState.toggle_data, id="toggle"),
        )


@pytest.fixture
def recharts_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start RechartsApp at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("recharts"),
        app_source=RechartsApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_line_chart(page: Page, recharts_app: AppHarness):
    """A line chart renders a surface, axis tick labels, and one curve per line.

    Args:
        page: Playwright page instance
        recharts_app: Harness for RechartsApp
    """
    assert recharts_app.frontend_url is not None
    page.goto(recharts_app.frontend_url)

    chart = page.locator("#line_chart")
    expect(chart.locator(".recharts-surface")).to_be_visible()
    # Two rx.recharts.line components -> two line curves.
    expect(chart.locator(".recharts-line-curve")).to_have_count(2)
    # X axis tick labels reflect the data_key="name" values.
    for label in ("Page A", "Page B", "Page C", "Page D"):
        expect(chart.get_by_text(label, exact=True)).to_be_visible()


def test_bar_chart(page: Page, recharts_app: AppHarness):
    """A bar chart renders one rectangle per data point.

    Args:
        page: Playwright page instance
        recharts_app: Harness for RechartsApp
    """
    assert recharts_app.frontend_url is not None
    page.goto(recharts_app.frontend_url)

    chart = page.locator("#bar_chart")
    expect(chart.locator(".recharts-surface")).to_be_visible()
    # One bar series with four data points -> four rectangles.
    expect(chart.locator(".recharts-bar-rectangle")).to_have_count(4)
    for label in ("Page A", "Page B", "Page C", "Page D"):
        expect(chart.get_by_text(label, exact=True)).to_be_visible()


def test_area_chart(page: Page, recharts_app: AppHarness):
    """An area chart renders a filled area path.

    Args:
        page: Playwright page instance
        recharts_app: Harness for RechartsApp
    """
    assert recharts_app.frontend_url is not None
    page.goto(recharts_app.frontend_url)

    chart = page.locator("#area_chart")
    expect(chart.locator(".recharts-surface")).to_be_visible()
    expect(chart.locator(".recharts-area-area")).to_have_count(1)


def test_pie_chart(page: Page, recharts_app: AppHarness):
    """A pie chart renders one sector per data point.

    Args:
        page: Playwright page instance
        recharts_app: Harness for RechartsApp
    """
    assert recharts_app.frontend_url is not None
    page.goto(recharts_app.frontend_url)

    chart = page.locator("#pie_chart")
    expect(chart.locator(".recharts-surface")).to_be_visible()
    expect(chart.locator(".recharts-pie-sector")).to_have_count(3)


def test_stateful_chart_updates(page: Page, recharts_app: AppHarness):
    """Mutating the state data re-renders the chart with new axis labels.

    Args:
        page: Playwright page instance
        recharts_app: Harness for RechartsApp
    """
    assert recharts_app.frontend_url is not None
    page.goto(recharts_app.frontend_url)

    chart = page.locator("#stateful_chart")
    expect(chart.locator(".recharts-surface")).to_be_visible()
    # Initial state shows month labels with three bars.
    expect(chart.locator(".recharts-bar-rectangle")).to_have_count(3)
    expect(chart.get_by_text("Jan", exact=True)).to_be_visible()

    page.locator("#toggle").click()

    # Toggled state swaps to the two-element quarter dataset.
    expect(chart.locator(".recharts-bar-rectangle")).to_have_count(2)
    expect(chart.get_by_text("Q1", exact=True)).to_be_visible()
    expect(chart.get_by_text("Jan", exact=True)).not_to_be_visible()
