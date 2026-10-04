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
        upload_id: str = "callback-upload"
        upload_count: int = 0
        uploaded: rx.Field[list[str]] = rx.field([])

        @rx.event
        async def handle_upload(self, uploads: list[rx.UploadFile]):
            """Record the names and contents received by an upload callback.

            Args:
                uploads: Uploaded files received by the backend.
            """
            self.uploaded = [
                f"{upload.name}:{(await upload.read()).decode()}" for upload in uploads
            ]
            self.upload_count += 1

        @rx.event
        def backend_upload_toast(self):
            """Offer upload actions from a serialized backend toast.

            Yields:
                A toast with upload action and cancel buttons.
            """
            upload_event = ToastActionState.handle_upload(
                rx.upload_files(upload_id=self.upload_id)  # pyright: ignore [reportArgumentType]
            )
            yield rx.toast(
                "Upload from backend toast",
                action={"label": "UploadAction", "on_click": upload_event},
                cancel={"label": "UploadCancel", "on_click": upload_event},
                duration=30000,
            )

        @rx.event
        def backend_upload_script(self):
            """Upload selected files from a serialized script callback.

            Yields:
                A script event with an upload callback.
            """
            yield rx.call_script(
                "1",
                callback=lambda _: ToastActionState.handle_upload(
                    rx.upload_files(upload_id=self.upload_id)  # pyright: ignore [reportArgumentType]
                ),
            )

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
            rx.upload(id="callback-upload"),
            rx.upload(id="other-upload"),
            rx.text(
                rx.selected_files("callback-upload").to_string(), id="selected-upload"
            ),
            rx.text(ToastActionState.uploaded.to_string(), id="uploaded"),
            rx.text(ToastActionState.upload_count, id="upload-count"),
            rx.button(
                "Upload Toast",
                id="upload-toast",
                on_click=rx.toast(
                    "Upload from frontend toast",
                    action={
                        "label": "UploadAction",
                        "on_click": ToastActionState.handle_upload(
                            rx.upload_files(upload_id="callback-upload")  # pyright: ignore [reportArgumentType]
                        ),
                    },
                    cancel={
                        "label": "UploadCancel",
                        "on_click": ToastActionState.handle_upload(
                            rx.upload_files(upload_id="callback-upload")  # pyright: ignore [reportArgumentType]
                        ),
                    },
                    duration=30000,
                ),
            ),
            rx.button(
                "Backend Upload Toast",
                id="backend-upload-toast",
                on_click=ToastActionState.backend_upload_toast,
            ),
            rx.button(
                "Script Upload",
                id="script-upload",
                on_click=rx.call_script(
                    "1",
                    callback=lambda _: ToastActionState.handle_upload(
                        rx.upload_files(upload_id="callback-upload")  # pyright: ignore [reportArgumentType]
                    ),
                ),
            ),
            rx.button(
                "Backend Script Upload",
                id="backend-script-upload",
                on_click=ToastActionState.backend_upload_script,
            ),
            rx.button(
                "Direct Upload",
                id="direct-upload",
                on_click=ToastActionState.handle_upload(
                    rx.upload_files(upload_id=ToastActionState.upload_id)  # pyright: ignore [reportArgumentType]
                ),
            ),
            rx.button(
                "Clear Selection",
                id="clear-selection",
                on_click=rx.clear_selected_files("callback-upload"),
            ),
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


@pytest.mark.parametrize(
    ("trigger", "action"),
    [
        ("upload-toast", "UploadAction"),
        ("upload-toast", "UploadCancel"),
        ("backend-upload-toast", "UploadAction"),
        ("backend-upload-toast", "UploadCancel"),
        ("script-upload", None),
        ("backend-script-upload", None),
        ("direct-upload", None),
    ],
)
def test_upload_callbacks(
    toast_app: AppHarness, page: Page, trigger: str, action: str | None
):
    """Upload the current selection through callbacks outside the upload component.

    Args:
        toast_app: AppHarness running the test app.
        page: Playwright page.
        trigger: ID of the button that creates the callback.
        action: Toast action to click, if applicable.
    """
    assert toast_app.frontend_url is not None
    page_errors: list[str] = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    page.goto(toast_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    page.locator('#other-upload input[type="file"]').set_input_files({
        "name": "other.txt",
        "mimeType": "text/plain",
        "buffer": b"other",
    })
    selected = page.locator('#callback-upload input[type="file"]')
    selected.set_input_files({
        "name": "before.txt",
        "mimeType": "text/plain",
        "buffer": b"before",
    })
    expect(page.locator("#selected-upload")).to_contain_text("before.txt")

    if action is not None:
        page.locator(f"#{trigger}").click()
        expect(page.get_by_role("button", name=action, exact=True)).to_be_visible()

    # A callback kept by a toast must read the selection when it is clicked.
    selected.set_input_files({
        "name": "current.txt",
        "mimeType": "text/plain",
        "buffer": b"current",
    })
    expect(page.locator("#selected-upload")).to_contain_text("current.txt")
    with page.expect_response(
        lambda response: (
            response.request.method == "POST" and response.url.endswith("/_upload")
        )
    ) as response:
        if action is not None:
            page.get_by_role("button", name=action, exact=True).click()
        else:
            page.locator(f"#{trigger}").click()
    assert response.value.ok
    expect(page.locator("#upload-count")).to_have_text("1")
    expect(page.locator("#uploaded")).to_have_text('["current.txt:current"]')

    page.locator("#clear-selection").click()
    expect(page.locator("#selected-upload")).to_have_text("[]")
    page.locator(f"#{trigger}").click()
    if action is not None:
        page.get_by_role("button", name=action, exact=True).click()
    expect(page.locator("#upload-count")).to_have_text("2")
    expect(page.locator("#uploaded")).to_have_text("[]")
    assert not page_errors, f"Frontend raised unexpected errors: {page_errors}"
