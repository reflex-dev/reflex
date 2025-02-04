"""Test case for displaying the connection banner when the websocket drops."""

import functools
from typing import Generator

import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness, WebDriver

from .utils import SessionStorage


def ConnectionBanner(is_reflex_cloud: bool = False):
    """App with a connection banner.

    Args:
        is_reflex_cloud: The value for config.is_reflex_cloud.
    """
    import asyncio

    import reflex as rx

    # Simulate reflex cloud deploy
    rx.config.get_config().is_reflex_cloud = is_reflex_cloud

    class State(rx.State):
        foo: int = 0

        @rx.event
        async def delay(self):
            await asyncio.sleep(5)

    def index():
        return rx.vstack(
            rx.text("Hello World"),
            rx.input(value=State.foo, read_only=True, id="counter"),
            rx.button(
                "Increment",
                id="increment",
                on_click=State.set_foo(State.foo + 1),  # pyright: ignore [reportAttributeAccessIssue]
            ),
            rx.button("Delay", id="delay", on_click=State.delay),
        )

    app = rx.App(_state=rx.State)
    app.add_page(index)


@pytest.fixture(
    params=[False, True], ids=["reflex_cloud_disabled", "reflex_cloud_enabled"]
)
def simulate_is_reflex_cloud(request) -> bool:
    """Fixture to simulate reflex cloud deployment.

    Args:
        request: pytest request fixture.

    Returns:
        True if reflex cloud is enabled, False otherwise.
    """
    return request.param


@pytest.fixture()
def connection_banner(
    tmp_path,
    simulate_is_reflex_cloud: bool,
) -> Generator[AppHarness, None, None]:
    """Start ConnectionBanner app at tmp_path via AppHarness.

    Args:
        tmp_path: pytest tmp_path fixture
        simulate_is_reflex_cloud: Whether is_reflex_cloud is set for the app.

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=functools.partial(
            ConnectionBanner, is_reflex_cloud=simulate_is_reflex_cloud
        ),
        app_name="connection_banner_reflex_cloud"
        if simulate_is_reflex_cloud
        else "connection_banner",
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
    except NoSuchElementException:
        return False
    else:
        return True


def has_cloud_banner(driver: WebDriver) -> bool:
    """Check if the cloud banner is displayed.

    Args:
        driver: Selenium webdriver instance.

    Returns:
        True if the banner is displayed, False otherwise.
    """
    try:
        driver.find_element(By.XPATH, "//*[ contains(text(), 'This app is paused') ]")
    except NoSuchElementException:
        return False
    else:
        return True


def _assert_token(connection_banner, driver):
    """Poll for backend to be up.

    Args:
        connection_banner: AppHarness instance.
        driver: Selenium webdriver instance.
    """
    ss = SessionStorage(driver)
    assert connection_banner._poll_for(lambda: ss.get("token") is not None), (
        "token not found"
    )


@pytest.mark.asyncio
async def test_connection_banner(connection_banner: AppHarness):
    """Test that the connection banner is displayed when the websocket drops.

    Args:
        connection_banner: AppHarness instance.
    """
    assert connection_banner.app_instance is not None
    assert connection_banner.backend is not None
    driver = connection_banner.frontend()

    _assert_token(connection_banner, driver)
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


@pytest.mark.asyncio
async def test_cloud_banner(
    connection_banner: AppHarness, simulate_is_reflex_cloud: bool
):
    """Test that the connection banner is displayed when the websocket drops.

    Args:
        connection_banner: AppHarness instance.
        simulate_is_reflex_cloud: Whether is_reflex_cloud is set for the app.
    """
    assert connection_banner.app_instance is not None
    assert connection_banner.backend is not None
    driver = connection_banner.frontend()

    driver.add_cookie({"name": "backend-enabled", "value": "truly"})
    driver.refresh()
    _assert_token(connection_banner, driver)
    assert connection_banner._poll_for(lambda: not has_cloud_banner(driver))

    driver.add_cookie({"name": "backend-enabled", "value": "false"})
    driver.refresh()
    if simulate_is_reflex_cloud:
        assert connection_banner._poll_for(lambda: has_cloud_banner(driver))
    else:
        _assert_token(connection_banner, driver)
        assert connection_banner._poll_for(lambda: not has_cloud_banner(driver))

    driver.delete_cookie("backend-enabled")
    driver.refresh()
    _assert_token(connection_banner, driver)
    assert connection_banner._poll_for(lambda: not has_cloud_banner(driver))
