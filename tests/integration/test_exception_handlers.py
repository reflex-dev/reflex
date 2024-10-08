"""Integration tests for event exception handlers."""

from __future__ import annotations

import time
from typing import Generator, Type

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from reflex.testing import AppHarness


def TestApp():
    """A test app for event exception handler integration."""
    import reflex as rx

    class TestAppConfig(rx.Config):
        """Config for the TestApp app."""

        pass

    class TestAppState(rx.State):
        """State for the TestApp app."""

        def divide_by_number(self, number: int):
            """Divide by number and print the result.

            Args:
                number: number to divide by

            """
            print(1 / number)

    app = rx.App(state=rx.State)

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
                on_click=lambda: TestAppState.divide_by_number(0),  # type: ignore
                id="induce-backend-error-btn",
            ),
        )


@pytest.fixture(scope="module")
def test_app(
    app_harness_env: Type[AppHarness], tmp_path_factory
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
        app_source=TestApp,  # type: ignore
    ) as harness:
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


def test_frontend_exception_handler_during_runtime(
    driver: WebDriver,
    capsys,
):
    """Test calling frontend exception handler during runtime.

    We send an event containing a call to a non-existent function in the frontend.
    This should trigger the default frontend exception handler.

    Args:
        driver: WebDriver instance.
        capsys: pytest fixture for capturing stdout and stderr.

    """
    reset_button = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.ID, "induce-frontend-error-btn"))
    )

    reset_button.click()

    # Wait for the error to be logged
    time.sleep(2)

    captured_default_handler_output = capsys.readouterr()
    assert (
        "induce_frontend_error" in captured_default_handler_output.out
        and "ReferenceError" in captured_default_handler_output.out
    )


def test_backend_exception_handler_during_runtime(
    driver: WebDriver,
    capsys,
):
    """Test calling backend exception handler during runtime.

    We invoke TestAppState.divide_by_zero to induce backend error.
    This should trigger the default backend exception handler.

    Args:
        driver: WebDriver instance.
        capsys: pytest fixture for capturing stdout and stderr.

    """
    reset_button = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.ID, "induce-backend-error-btn"))
    )

    reset_button.click()

    # Wait for the error to be logged
    time.sleep(2)

    captured_default_handler_output = capsys.readouterr()
    assert (
        "divide_by_number" in captured_default_handler_output.out
        and "ZeroDivisionError" in captured_default_handler_output.out
    )
