"""Test case for displaying the connection banner when the websocket drops."""

import functools
from collections.abc import Generator

import pytest
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from reflex import constants
from reflex.testing import AppHarness, WebDriver
from reflex.utils import processes

from .utils import SessionStorage


def ConnectionBanner(simulate_compile_context: str):
    """App with a connection banner.

    Args:
        simulate_compile_context: The context to run the app with.
    """
    import asyncio

    import reflex as rx
    from reflex.constants import CompileContext
    from reflex.environment import environment

    environment.REFLEX_COMPILE_CONTEXT.set(CompileContext(simulate_compile_context))

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

    app = rx.App()
    app.add_page(index)


@pytest.fixture(
    params=[constants.CompileContext.RUN, constants.CompileContext.DEPLOY],
    ids=["compile_context_run", "compile_context_deploy"],
)
def simulate_compile_context(request) -> constants.CompileContext:
    """Fixture to simulate reflex cloud deployment.

    Args:
        request: pytest request fixture.

    Returns:
        The context to run the app with.
    """
    return request.param


@pytest.fixture
def connection_banner(
    tmp_path,
    simulate_compile_context: constants.CompileContext,
) -> Generator[AppHarness, None, None]:
    """Start ConnectionBanner app at tmp_path via AppHarness.

    Args:
        tmp_path: pytest tmp_path fixture
        simulate_compile_context: Which context to run the app with.

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=functools.partial(
            ConnectionBanner, simulate_compile_context=simulate_compile_context.value
        ),
        app_name=(
            "connection_banner_reflex_cloud"
            if simulate_compile_context == constants.CompileContext.DEPLOY
            else "connection_banner"
        ),
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
    assert connection_banner.reflex_process is not None
    driver = connection_banner.frontend()

    _assert_token(connection_banner, driver)
    AppHarness.expect(lambda: not has_error_modal(driver))

    delay_button = driver.find_element(By.ID, "delay")
    increment_button = driver.find_element(By.ID, "increment")
    counter_element = driver.find_element(By.ID, "counter")

    # Increment the counter
    increment_button.click()
    assert connection_banner.poll_for_value(counter_element, exp_not_equal="0") == "1"

    # Start an long event before killing the backend, to mark event_processing=true
    delay_button.click()

    # Kill reflex
    connection_banner._stop_reflex()

    # Error modal should now be displayed
    AppHarness.expect(lambda: has_error_modal(driver), timeout=30, step=1)

    # Increment the counter with backend down
    increment_button.click()
    assert connection_banner.poll_for_value(counter_element, exp_not_equal="0") == "1"

    # Bring the backend back up once the port is free'd.
    if result := AppHarness._poll_for(
        lambda: processes.handle_port(
            "backend", connection_banner.backend_port or 0, auto_increment=False
        ),
        timeout=120,
    ):
        print(f"Port {result} is now free.")
    assert result, f"Port is not free: {connection_banner.backend_port} after timeout."
    connection_banner._start_subprocess(frontend=False)

    # Create a new StateManager to avoid async loop affinity issues w/ redis
    await connection_banner._reset_backend_state_manager()

    # Banner should be gone now
    AppHarness.expect(lambda: not has_error_modal(driver))

    # Count should have incremented after coming back up
    assert connection_banner.poll_for_value(counter_element, exp_not_equal="1") == "2"


@pytest.mark.asyncio
async def test_cloud_banner(
    connection_banner: AppHarness, simulate_compile_context: constants.CompileContext
):
    """Test that the connection banner is displayed when the websocket drops.

    Args:
        connection_banner: AppHarness instance.
        simulate_compile_context: Which context to set for the app.
    """
    assert connection_banner.app_instance is not None
    assert connection_banner.reflex_process is not None
    driver = connection_banner.frontend()

    driver.add_cookie({"name": "backend-enabled", "value": "truly"})
    driver.refresh()
    _assert_token(connection_banner, driver)
    AppHarness.expect(lambda: not has_cloud_banner(driver))

    driver.add_cookie({"name": "backend-enabled", "value": "false"})
    driver.refresh()
    if simulate_compile_context == constants.CompileContext.DEPLOY:
        AppHarness.expect(lambda: has_cloud_banner(driver))
    else:
        _assert_token(connection_banner, driver)
        AppHarness.expect(lambda: not has_cloud_banner(driver))

    driver.delete_cookie("backend-enabled")
    driver.refresh()
    _assert_token(connection_banner, driver)
    AppHarness.expect(lambda: not has_cloud_banner(driver))
