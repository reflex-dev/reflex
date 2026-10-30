"""Integration tests for event exception handlers."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness, AppHarnessProd

pytestmark = [pytest.mark.ignore_console_error]


def TestApp():
    """A test app for event exception handler integration."""
    import reflex as rx

    class TestAppConfig(rx.Config):
        """Config for the TestApp app."""

    class TestAppState(rx.State):
        """State for the TestApp app."""

        react_error: bool = False

        @rx.event
        def set_react_error(self, value: bool):
            self.react_error = value

        def divide_by_number(self, number: int):
            """Divide by number and print the result.

            Args:
                number: number to divide by.
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
                on_click=TestAppState.set_react_error(True),
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
    """Start TestApp in dev or production mode.

    Yields:
        The running app harness.
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("test_app"),
        app_name=f"testapp_{app_harness_env.__name__.lower()}",
        app_source=TestApp,
    ) as harness:
        yield harness


def _open_app(test_app: AppHarness, page: Page) -> None:
    """Open the test app in the browser."""
    assert test_app.app_instance is not None, "app is not running"
    assert test_app.frontend_url is not None
    page.goto(test_app.frontend_url)


def test_frontend_exception_handler_during_runtime(
    test_app: AppHarness,
    page: Page,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A missing frontend function reaches the frontend exception handler."""
    _open_app(test_app, page)
    button = page.locator("#induce-frontend-error-btn")
    expect(button).to_be_enabled()
    button.click()

    assert AppHarness._poll_for(
        lambda: (
            "induce_frontend_error" in caplog.text and "ReferenceError" in caplog.text
        )
    ), caplog.text


def test_backend_exception_handler_during_runtime(
    test_app: AppHarness,
    page: Page,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A backend exception reaches the backend exception handler."""
    _open_app(test_app, page)
    button = page.locator("#induce-backend-error-btn")
    expect(button).to_be_enabled()
    button.click()

    assert AppHarness._poll_for(
        lambda: "divide_by_number" in caplog.text and "ZeroDivisionError" in caplog.text
    ), caplog.text


def test_frontend_exception_handler_with_react(
    test_app: AppHarness,
    page: Page,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An invalid React child reaches the frontend exception handler."""
    _open_app(test_app, page)
    button = page.locator("#induce-react-error-btn")
    expect(button).to_be_enabled()
    button.click()

    if isinstance(test_app, AppHarnessProd):
        expected_error = "Error: Minified React error #31"
    else:
        expected_error = "Error: Objects are not valid as a React child (found: object with keys {invalid})"
    assert AppHarness._poll_for(lambda: expected_error in caplog.text), caplog.text
