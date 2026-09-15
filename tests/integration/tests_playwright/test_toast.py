"""Integration tests for rx.toast action and cancel buttons.

Regression coverage for the frontend ``ReferenceError: queueEvents is not
defined`` that fired when clicking a toast action/cancel button whose
``on_click`` was queued via a toast triggered directly from a frontend event.
"""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def ToastApp():
    """App firing toasts with action/cancel buttons from frontend and backend."""
    import reflex as rx

    class ToastActionState(rx.State):
        undone: int = 0
        dismissed: int = 0

        @rx.event
        def undo(self):
            self.undone += 1

        @rx.event
        def dismiss(self):
            self.dismissed += 1

        @rx.event
        def backend_toast(self):
            yield rx.toast(
                "Backend toast",
                action={"label": "BackendUndo", "on_click": ToastActionState.undo},
                duration=30000,
            )

    @rx.page("/")
    def index():
        return rx.box(
            rx.input(
                value=ToastActionState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.button(
                "Show Toast",
                on_click=rx.toast(
                    "Frontend toast",
                    action={"label": "Undo", "on_click": ToastActionState.undo},
                    cancel={
                        "label": "Dismiss",
                        "on_click": ToastActionState.dismiss,
                    },
                    duration=30000,
                ),
                id="show-toast",
            ),
            rx.button(
                "Backend Toast",
                on_click=ToastActionState.backend_toast,
                id="show-backend-toast",
            ),
            rx.text(ToastActionState.undone, id="undone"),
            rx.text(ToastActionState.dismissed, id="dismissed"),
        )

    app = rx.App()  # noqa: F841


@pytest.fixture(scope="module")
def toast_app(
    app_harness_env: type[AppHarness], tmp_path_factory
) -> Generator[AppHarness, None, None]:
    """Start ToastApp in dev or prod mode via AppHarness.

    Args:
        app_harness_env: AppHarness (dev) or AppHarnessProd (prod).
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness instance.
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("toast_app"),
        app_source=ToastApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_toast_action_buttons_queue_events(toast_app: AppHarness, page: Page):
    """Toast action/cancel buttons trigger their on_click state events.

    Args:
        toast_app: AppHarness running the test app.
        page: Playwright page.
    """
    assert toast_app.frontend_url is not None

    page_errors: list[str] = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    page.goto(toast_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    # Toast fired from a frontend event trigger: action button.
    page.locator("#show-toast").click()
    toast = page.locator("[data-sonner-toast]")
    expect(toast).to_be_visible()
    toast.get_by_role("button", name="Undo").click()
    expect(page.locator("#undone")).to_have_text("1")
    expect(toast).not_to_be_visible()

    # Toast fired from a frontend event trigger: cancel button.
    page.locator("#show-toast").click()
    expect(toast).to_be_visible()
    toast.get_by_role("button", name="Dismiss").click()
    expect(page.locator("#dismissed")).to_have_text("1")
    expect(toast).not_to_be_visible()

    # Toast yielded from a backend event handler: action button.
    page.locator("#show-backend-toast").click()
    expect(toast).to_be_visible()
    toast.get_by_role("button", name="BackendUndo").click()
    expect(page.locator("#undone")).to_have_text("2")

    assert not page_errors, f"Frontend raised unexpected errors: {page_errors}"
