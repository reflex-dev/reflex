"""Test large state."""

import time

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness, WebDriver


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


def get_driver(large_state) -> WebDriver:
    """Get an instance of the browser open to the large_state app.

    Args:
        large_state: harness for LargeState app

    Returns:
        WebDriver instance.
    """
    assert large_state.app_instance is not None, "app is not running"
    return large_state.frontend()


@pytest.mark.parametrize("var_count", [1, 10, 100, 1000, 10000])
def test_large_state(var_count: int, tmp_path_factory, benchmark):
    """Measure how long it takes for button click => state update to round trip.

    Args:
        var_count: number of variables to store in the state
        tmp_path_factory: pytest fixture
        benchmark: pytest fixture

    Raises:
        TimeoutError: if the state doesn't update within 30 seconds
    """
    large_state_rendered = _large_state_app_template(var_count)

    with AppHarness.create(
        root=tmp_path_factory.mktemp("large_state"),
        app_source=large_state_rendered,
        app_name="large_state",
    ) as large_state:
        driver = get_driver(large_state)
        try:
            assert large_state.app_instance is not None
            button = AppHarness.poll_for_or_raise_timeout(
                lambda: driver.find_element(By.ID, "button")
            )

            t = time.time()
            while button.text != "0":
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
                while button.text != str(times_clicked):
                    time.sleep(0.005)
                    if time.time() - t > timeout:
                        msg = "Timeout waiting for state update"
                        raise TimeoutError(msg)

            benchmark(round_trip, clicks=10, timeout=30.0)
        finally:
            driver.quit()
