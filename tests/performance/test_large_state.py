"""Browser benchmark for state update latency at increasing state sizes."""

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


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
@pytest.mark.parametrize("var_count", [1, 10, 100, 1000, 10000])
def test_large_state(var_count: int, tmp_path_factory, benchmark, page: Page):
    """Measure the button-to-state-update round trip for large states.

    Args:
        var_count: Number of variables to store in the state.
        tmp_path_factory: Pytest fixture for temporary app directories.
        benchmark: Pytest benchmark fixture.
        page: Playwright page for the browser interaction.
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
