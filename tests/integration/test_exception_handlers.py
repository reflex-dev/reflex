"""Integration tests for event exception handlers."""

from __future__ import annotations

import time
from collections.abc import Callable, Generator

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from reflex.testing import AppHarness, AppHarnessProd


def TestApp():
    """A test app for event exception handler integration."""
    import reflex as rx

    class TestAppConfig(rx.Config):
        """Config for the TestApp app."""

    class TestAppState(rx.State):
        """State for the TestApp app."""

        react_error: bool = False

        def divide_by_number(self, number: int):
            """Divide by number and print the result.

            Args:
                number: number to divide by

            """
            print(1 / number)

    app = rx.App()

    @app.add_page
    def index():
        return rx.vstack(
            rx.button(
                "induce_frontend_error",
                on_click=rx.call_script("induce_frontend_error()"),
                id="induce-frontend-error-btn",
            ),
            rx.button(
                "induce_backend_error",
                on_click=lambda: TestAppState.divide_by_number(0),  # pyright: ignore [reportCallIssue]
                id="induce-backend-error-btn",
            ),
            rx.button(
                "induce_react_error",
                on_click=TestAppState.set_react_error(True),  # pyright: ignore [reportAttributeAccessIssue]
                id="induce-react-error-btn",
            ),
            rx.box(
                rx.cond(
                    TestAppState.react_error,
                    rx.Var.create({"invalid": "cannot have object as child"}),
                    "",
                ),
            ),
        )


@pytest.fixture(scope="module")
def test_app(
    app_harness_env: type[AppHarness], tmp_path_factory
) -> Generator[AppHarness, None, None]:
    """Start TestApp app at tmp_path via AppHarness.

    Args:
        app_harness_env: either AppHarness (dev) or AppHarnessProd (prod)
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance

    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("test_app"),
        app_name=f"testapp_{app_harness_env.__name__.lower()}",
        app_source=TestApp,
    ) as harness:
        # disable console.error checking for this test
        harness.reflex_process_error_log_path = None
        yield harness


@pytest.fixture
def driver(test_app: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the test_app app.

    Args:
        test_app: harness for TestApp app

    Yields:
        WebDriver instance.

    """
    assert test_app.app_instance is not None, "app is not running"
    driver = test_app.frontend()
    try:
        yield driver
    finally:
        driver.quit()


@pytest.fixture
def get_reflex_output(test_app: AppHarness) -> Callable[[], str]:
    """Get the output of the reflex process.

    Args:
        test_app: harness for TestApp app

    Returns:
        The output of the reflex process.
    """
    assert test_app.reflex_process is not None, "app is not running"
    assert test_app.reflex_process_log_path is not None, (
        "reflex process log path is not set"
    )
    initial_offset = test_app.reflex_process_log_path.stat().st_size

    def f() -> str:
        assert test_app.reflex_process_log_path is not None, (
            "reflex process log path is not set"
        )
        return test_app.reflex_process_log_path.read_bytes()[initial_offset:].decode(
            "utf-8"
        )

    return f


def test_frontend_exception_handler_during_runtime(
    driver: WebDriver, get_reflex_output: Callable[[], str]
):
    """Test calling frontend exception handler during runtime.

    We send an event containing a call to a non-existent function in the frontend.
    This should trigger the default frontend exception handler.

    Args:
        driver: WebDriver instance.
        get_reflex_output: Function to get the reflex process output.

    """
    reset_button = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.ID, "induce-frontend-error-btn"))
    )

    reset_button.click()

    # Wait for the error to be logged
    time.sleep(2)

    captured_default_handler_output = get_reflex_output()
    assert "induce_frontend_error" in captured_default_handler_output
    assert "ReferenceError" in captured_default_handler_output


def test_backend_exception_handler_during_runtime(
    driver: WebDriver,
    get_reflex_output: Callable[[], str],
):
    """Test calling backend exception handler during runtime.

    We invoke TestAppState.divide_by_zero to induce backend error.
    This should trigger the default backend exception handler.

    Args:
        driver: WebDriver instance.
        get_reflex_output: Function to get the reflex process output.

    """
    reset_button = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.ID, "induce-backend-error-btn"))
    )

    reset_button.click()

    # Wait for the error to be logged
    time.sleep(2)

    captured_default_handler_output = get_reflex_output()
    assert "divide_by_number" in captured_default_handler_output
    assert "ZeroDivisionError" in captured_default_handler_output


def test_frontend_exception_handler_with_react(
    test_app: AppHarness,
    driver: WebDriver,
    get_reflex_output: Callable[[], str],
):
    """Test calling frontend exception handler during runtime.

    Render an object as a react child, which is invalid.

    Args:
        test_app: harness for TestApp app
        driver: WebDriver instance.
        get_reflex_output: Function to get the reflex process output.

    """
    reset_button = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.ID, "induce-react-error-btn"))
    )

    reset_button.click()

    # Wait for the error to be logged
    time.sleep(2)

    captured_default_handler_output = get_reflex_output()
    if isinstance(test_app, AppHarnessProd):
        assert "Error: Minified React error #31" in captured_default_handler_output
    else:
        assert (
            "Error: Objects are not valid as a React child (found: object with keys \n{invalid})"
            in captured_default_handler_output
        )
