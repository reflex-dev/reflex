"""Integration test for ``rx.el.textarea(enter_key_submit=True)``.

Regression coverage for the frontend ``ReferenceError: enterKeySubmitOnKeyDown
is not defined`` that fired when the helper JS was dropped during plugin-based
compilation. Pressing Enter inside the textarea must submit the parent form
without raising a runtime exception in the browser.
"""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def EnterKeySubmitApp():
    """Form containing a textarea that submits on Enter."""
    import reflex as rx

    class State(rx.State):
        submitted_value: str = ""

        @rx.event
        def on_submit(self, form_data: dict):
            self.submitted_value = form_data.get("t", "")

    @rx.page("/")
    def index():
        return rx.box(
            rx.input(
                value=State.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.el.form(
                rx.el.textarea(
                    enter_key_submit=True,
                    name="t",
                    id="ta",
                ),
                on_submit=State.on_submit,
                custom_attrs={"action": "/invalid"},
            ),
            rx.text(State.submitted_value, id="submitted"),
        )

    app = rx.App()  # noqa: F841


@pytest.fixture(scope="module")
def enter_key_submit_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start EnterKeySubmitApp via AppHarness.

    Args:
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness instance.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("enter_key_submit_app"),
        app_source=EnterKeySubmitApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_textarea_enter_key_submits_form(enter_key_submit_app: AppHarness, page: Page):
    """Pressing Enter in the textarea submits the form and raises no JS errors.

    Args:
        enter_key_submit_app: AppHarness running the test app.
        page: Playwright page.
    """
    assert enter_key_submit_app.frontend_url is not None

    page_errors: list[str] = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    page.goto(enter_key_submit_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    textarea = page.locator("#ta")
    textarea.click()
    textarea.fill("hello")
    textarea.press("Enter")

    expect(page.locator("#submitted")).to_have_text("hello")
    assert not page_errors, f"Frontend raised unexpected errors: {page_errors}"


def test_textarea_shift_enter_inserts_newline(
    enter_key_submit_app: AppHarness, page: Page
):
    """Shift+Enter must add a newline rather than submit the form.

    Args:
        enter_key_submit_app: AppHarness running the test app.
        page: Playwright page.
    """
    assert enter_key_submit_app.frontend_url is not None

    page.goto(enter_key_submit_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    textarea = page.locator("#ta")
    textarea.click()
    textarea.type("line1")
    textarea.press("Shift+Enter")
    textarea.type("line2")
    textarea.press("Enter")

    expect(page.locator("#submitted")).to_have_text("line1\nline2")
