"""Test large state."""

import time

import pytest
from playwright.sync_api import Page

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


@pytest.mark.parametrize("var_count", [1, 10, 100, 1000, 10000])
def test_large_state(var_count: int, tmp_path_factory, benchmark, page: Page):
    """Measure how long it takes for button click => state update to round trip.

    Args:
        var_count: number of variables to store in the state
        tmp_path_factory: pytest fixture
        benchmark: pytest fixture
        page: Playwright Page instance.

    Raises:
        TimeoutError: if the state doesn't update within 30 seconds
    """
    large_state_rendered = _large_state_app_template(var_count)

    with AppHarness.create(
        root=tmp_path_factory.mktemp("large_state"),
        app_source=large_state_rendered,
        app_name="large_state",
    ) as large_state:
        assert large_state.app_instance is not None
        assert large_state.frontend_url is not None
        page.goto(large_state.frontend_url)

        button = page.locator("#button")

        t = time.time()
        while button.text_content() != "0":
            time.sleep(0.1)
            if time.time() - t > 30.0:
                msg = "Timeout waiting for initial state"
                raise TimeoutError(msg)

        times_clicked = 0

        def round_trip(clicks: int, timeout: float):
            t = time.time()
            for _ in range(clicks):
                button.click()
            nonlocal times_clicked
            times_clicked += clicks
            while button.text_content() != str(times_clicked):
                time.sleep(0.005)
                if time.time() - t > timeout:
                    msg = "Timeout waiting for state update"
                    raise TimeoutError(msg)

        benchmark(round_trip, clicks=10, timeout=30.0)
