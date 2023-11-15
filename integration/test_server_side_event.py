"""Integration tests for special server side events."""
import time
from typing import Generator

import pytest
from selenium.webdriver.common.by import By

from nextpy.core.testing import AppHarness


def ServerSideEvent():
    """App with inputs set via event handlers and set_value."""
    import nextpy as xt

    class SSState(xt.State):
        def set_value_yield(self):
            yield xt.set_value("a", "")
            yield xt.set_value("b", "")
            yield xt.set_value("c", "")

        def set_value_yield_return(self):
            yield xt.set_value("a", "")
            yield xt.set_value("b", "")
            return xt.set_value("c", "")

        def set_value_return(self):
            return [
                xt.set_value("a", ""),
                xt.set_value("b", ""),
                xt.set_value("c", ""),
            ]

        def set_value_return_c(self):
            return xt.set_value("c", "")

    app = xt.App(state=SSState)

    @app.add_page
    def index():
        return xt.fragment(
            xt.input(
                id="token", value=SSState.router.session.client_token, is_read_only=True
            ),
            xt.input(default_value="a", id="a"),
            xt.input(default_value="b", id="b"),
            xt.input(default_value="c", id="c"),
            xt.button(
                "Clear Immediate",
                id="clear_immediate",
                on_click=[
                    xt.set_value("a", ""),
                    xt.set_value("b", ""),
                    xt.set_value("c", ""),
                ],
            ),
            xt.button(
                "Clear Chained Yield",
                id="clear_chained_yield",
                on_click=SSState.set_value_yield,
            ),
            xt.button(
                "Clear Chained Yield+Return",
                id="clear_chained_yield_return",
                on_click=SSState.set_value_yield_return,
            ),
            xt.button(
                "Clear Chained Return",
                id="clear_chained_return",
                on_click=SSState.set_value_return,
            ),
            xt.button(
                "Clear C Return",
                id="clear_return_c",
                on_click=SSState.set_value_return_c,
            ),
        )

    app.compile()


@pytest.fixture(scope="session")
def server_side_event(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start ServerSideEvent app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("server_side_event"),
        app_source=ServerSideEvent,  # type: ignore
    ) as harness:
        yield harness


@pytest.fixture
def driver(server_side_event: AppHarness):
    """Get an instance of the browser open to the server_side_event app.


    Args:
        server_side_event: harness for ServerSideEvent app

    Yields:
        WebDriver instance.
    """
    assert server_side_event.app_instance is not None, "app is not running"
    driver = server_side_event.frontend()
    try:
        token_input = driver.find_element(By.ID, "token")
        assert token_input
        # wait for the backend connection to send the token
        token = server_side_event.poll_for_value(token_input)
        assert token is not None

        yield driver
    finally:
        driver.quit()


@pytest.mark.parametrize(
    "button_id",
    [
        "clear_immediate",
        "clear_chained_yield",
        "clear_chained_yield_return",
        "clear_chained_return",
    ],
)
def test_set_value(driver, button_id: str):
    """Call set_value as an event chain, via yielding, via yielding with return.

    Args:
        driver: selenium WebDriver open to the app
        button_id: id of the button to click (parametrized)
    """
    input_a = driver.find_element(By.ID, "a")
    input_b = driver.find_element(By.ID, "b")
    input_c = driver.find_element(By.ID, "c")
    btn = driver.find_element(By.ID, button_id)

    assert input_a
    assert input_b
    assert input_c
    assert btn

    assert input_a.get_attribute("value") == "a"
    assert input_b.get_attribute("value") == "b"
    assert input_c.get_attribute("value") == "c"
    btn.click()
    time.sleep(0.2)
    assert input_a.get_attribute("value") == ""
    assert input_b.get_attribute("value") == ""
    assert input_c.get_attribute("value") == ""


def test_set_value_return_c(driver):
    """Call set_value returning single event.

    Args:
        driver: selenium WebDriver open to the app
    """
    input_a = driver.find_element(By.ID, "a")
    input_b = driver.find_element(By.ID, "b")
    input_c = driver.find_element(By.ID, "c")
    btn = driver.find_element(By.ID, "clear_return_c")

    assert input_a
    assert input_b
    assert input_c
    assert btn

    assert input_a.get_attribute("value") == "a"
    assert input_b.get_attribute("value") == "b"
    assert input_c.get_attribute("value") == "c"
    btn.click()
    time.sleep(0.2)
    assert input_a.get_attribute("value") == "a"
    assert input_b.get_attribute("value") == "b"
    assert input_c.get_attribute("value") == ""
