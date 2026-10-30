"""Browser benchmark for state update latency at increasing state sizes."""

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness
from tests.benchmarks.support import BenchmarkResult, PerformanceReport


def _large_state_app_template(var_count: int) -> str:
    var_part = "\n".join(
        f'    var{i}: str = "{i}" * 10000' for i in range(1, var_count)
    )
    return f"""
import reflex as rx

class State(rx.State):
    var0: int = 0
    {var_part}

    def increment_var0(self):
        self.var0 += 1


def index() -> rx.Component:
    return rx.box(rx.button(State.var0, on_click=State.increment_var0, id="button"))

app = rx.App()
app.add_page(index)
"""


@pytest.mark.performance
def test_large_state(
    var_count: int,
    tmp_path_factory,
    benchmark,
    page: Page,
    performance_output,
    performance_scale: str,
):
    """Measure the button-to-state-update round trip for large states.

    Args:
        var_count: Number of variables to store in the state.
        tmp_path_factory: Pytest fixture for temporary app directories.
        benchmark: Pytest benchmark fixture.
        page: Playwright page for the browser interaction.
        performance_output: Directory for benchmark artifacts.
        performance_scale: Selected performance scenario scale.
    """
    app_source = _large_state_app_template(var_count)

    with AppHarness.create(
        root=tmp_path_factory.mktemp("large_state"),
        app_source=app_source,
        app_name="large_state",
    ) as large_state:
        assert large_state.app_instance is not None
        assert large_state.frontend_url is not None
        page.goto(large_state.frontend_url)
        button = page.locator("#button")
        expect(button).to_have_text("0", timeout=30_000)

        times_clicked = 0

        def round_trip(clicks: int, timeout: float) -> None:
            nonlocal times_clicked
            for _ in range(clicks):
                button.click()
            times_clicked += clicks
            expect(button).to_have_text(str(times_clicked), timeout=timeout * 1000)

        benchmark(round_trip, clicks=10, timeout=30.0)
        stats = benchmark.stats.stats
        report = PerformanceReport(
            "large-state",
            metadata={"scale": performance_scale},
        )
        report.add(
            BenchmarkResult(
                "state_update_10_clicks",
                {"variables": var_count, "clicks": 10},
                [duration * 1000 for duration in stats.data],
                {},
                measurement_iterations=stats.rounds,
            )
        )
        report.write(performance_output / f"large-state-{var_count}.json")
