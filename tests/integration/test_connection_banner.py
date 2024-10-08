"""Test case for displaying the connection banner when the websocket drops."""

from typing import Generator

import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness, WebDriver

from .utils import SessionStorage


def ConnectionBanner():
    """App with a connection banner."""
    import asyncio

    import reflex as rx

    class State(rx.State):
        foo: int = 0

        async def delay(self):
            await asyncio.sleep(5)

    def index():
        return rx.vstack(
            rx.text("Hello World"),
            rx.input(value=State.foo, read_only=True, id="counter"),
            rx.button(
                "Increment",
                id="increment",
                on_click=State.set_foo(State.foo + 1),  # type: ignore
            ),
            rx.button("Delay", id="delay", on_click=State.delay),
        )

    app = rx.App(state=rx.State)
    app.add_page(index)


@pytest.fixture()
def connection_banner(tmp_path) -> Generator[AppHarness, None, None]:
    """Start ConnectionBanner app at tmp_path via AppHarness.

    Args:
        tmp_path: pytest tmp_path fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=ConnectionBanner,  # type: ignore
    ) as harness:
        yield harness


CONNECTION_ERROR_XPATH = "//*[ contains(text(), 'Cannot connect to server') ]"


def has_error_modal(driver: WebDriver) -> bool:
    """Check if the connection error modal is displayed.

    Args:
        driver: Selenium webdriver instance.

    Returns:
        True if the modal is displayed, False otherwise.
    """
    try:
        driver.find_element(By.XPATH, CONNECTION_ERROR_XPATH)
        return True
    except NoSuchElementException:
        return False


@pytest.mark.asyncio
async def test_connection_banner(connection_banner: AppHarness):
    """Test that the connection banner is displayed when the websocket drops.

    Args:
        connection_banner: AppHarness instance.
    """
    assert connection_banner.app_instance is not None
    assert connection_banner.backend is not None
    driver = connection_banner.frontend()

    ss = SessionStorage(driver)
    assert connection_banner._poll_for(
        lambda: ss.get("token") is not None
    ), "token not found"

    assert connection_banner._poll_for(lambda: not has_error_modal(driver))

    delay_button = driver.find_element(By.ID, "delay")
    increment_button = driver.find_element(By.ID, "increment")
    counter_element = driver.find_element(By.ID, "counter")

    # Increment the counter
    increment_button.click()
    assert connection_banner.poll_for_value(counter_element, exp_not_equal="0") == "1"

    # Start an long event before killing the backend, to mark event_processing=true
    delay_button.click()

    # Get the backend port
    backend_port = connection_banner._poll_for_servers().getsockname()[1]

    # Kill the backend
    connection_banner.backend.should_exit = True
    if connection_banner.backend_thread is not None:
        connection_banner.backend_thread.join()

    # Error modal should now be displayed
    assert connection_banner._poll_for(lambda: has_error_modal(driver))

    # Increment the counter with backend down
    increment_button.click()
    assert connection_banner.poll_for_value(counter_element, exp_not_equal="0") == "1"

    # Bring the backend back up
    connection_banner._start_backend(port=backend_port)

    # Create a new StateManager to avoid async loop affinity issues w/ redis
    await connection_banner._reset_backend_state_manager()

    # Banner should be gone now
    assert connection_banner._poll_for(lambda: not has_error_modal(driver))

    # Count should have incremented after coming back up
    assert connection_banner.poll_for_value(counter_element, exp_not_equal="1") == "2"
