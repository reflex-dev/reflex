"""Test case for displaying the connection banner when the websocket drops."""

from typing import Generator

import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from nextpy.core.testing import AppHarness, WebDriver


def ConnectionBanner():
    """App with a connection banner."""
    import nextpy as xt

    class State(xt.State):
        foo: int = 0

    def index():
        return xt.text("Hello World")

    app = xt.App(state=State)
    app.add_page(index)
    app.compile()


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


CONNECTION_ERROR_XPATH = "//*[ text() = 'Connection Error' ]"


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


def test_connection_banner(connection_banner: AppHarness):
    """Test that the connection banner is displayed when the websocket drops.

    Args:
        connection_banner: AppHarness instance.
    """
    assert connection_banner.app_instance is not None
    assert connection_banner.backend is not None
    driver = connection_banner.frontend()

    connection_banner._poll_for(lambda: not has_error_modal(driver))

    # Get the backend port
    backend_port = connection_banner._poll_for_servers().getsockname()[1]

    # Kill the backend
    connection_banner.backend.should_exit = True
    if connection_banner.backend_thread is not None:
        connection_banner.backend_thread.join()

    # Error modal should now be displayed
    connection_banner._poll_for(lambda: has_error_modal(driver))

    # Bring the backend back up
    connection_banner._start_backend(port=backend_port)

    # Banner should be gone now
    connection_banner._poll_for(lambda: not has_error_modal(driver))
