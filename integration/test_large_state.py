"""Test large state."""

import time

import jinja2
import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness, WebDriver

LARGE_STATE_APP_TEMPLATE = """
import reflex as rx

class State(rx.State):
    var0: int = 0
    {% for i in range(1, var_count) %}
    var{{ i }}: str = "{{ i }}" * 10000
    {% endfor %}

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
    template = jinja2.Template(LARGE_STATE_APP_TEMPLATE)
    large_state_rendered = template.render(var_count=var_count)

    with AppHarness.create(
        root=tmp_path_factory.mktemp(f"large_state"),
        app_source=large_state_rendered,
        app_name="large_state",
    ) as large_state:
        driver = get_driver(large_state)
        try:
            assert large_state.app_instance is not None
            button = driver.find_element(By.ID, "button")

            t = time.time()
            while button.text != "0":
                time.sleep(0.1)
                if time.time() - t > 30.0:
                    raise TimeoutError("Timeout waiting for initial state")

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
                        raise TimeoutError("Timeout waiting for state update")

            benchmark(round_trip, clicks=10, timeout=30.0)
        finally:
            driver.quit()
