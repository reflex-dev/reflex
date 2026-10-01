"""Integration test for ``rx.debounce_input`` wrapping native ``rx.el`` elements.

Regression coverage for the frontend ``ReferenceError: input is not defined``
that fired when DebounceInput passed a native DOM tag (e.g. ``rx.el.input``)
as a bare identifier in the ``element`` prop instead of a string literal.
"""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def DebounceNativeElementApp():
    """App wrapping native DOM elements in rx.debounce_input."""
    import reflex as rx

    class State(rx.State):
        text: str = ""
        area: str = ""

        @rx.event
        def set_text(self, value: str):
            self.text = value

        @rx.event
        def set_area(self, value: str):
            self.area = value

    @rx.page("/")
    def index():
        return rx.box(
            rx.input(
                value=State.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.debounce_input(
                rx.el.input(
                    placeholder="Search...",
                    on_change=State.set_text,
                    id="native-input",
                ),
                debounce_timeout=50,
            ),
            rx.debounce_input(
                rx.el.textarea(
                    on_change=State.set_area,
                    id="native-textarea",
                ),
                debounce_timeout=50,
            ),
            rx.text(State.text, id="text-value"),
            rx.text(State.area, id="area-value"),
        )

    app = rx.App()  # noqa: F841


@pytest.fixture(scope="module")
def debounce_native_element_app(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start DebounceNativeElementApp via AppHarness.

    Args:
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness instance.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("debounce_native_element_app"),
        app_source=DebounceNativeElementApp,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_debounce_wrapped_native_elements(
    debounce_native_element_app: AppHarness, page: Page
):
    """Debounced native input/textarea render and propagate changes to state.

    Args:
        debounce_native_element_app: AppHarness running the test app.
        page: Playwright page.
    """
    assert debounce_native_element_app.frontend_url is not None

    page_errors: list[str] = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    page.goto(debounce_native_element_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    # DebounceInput must render the actual native tags with carried props.
    native_input = page.locator("input#native-input")
    expect(native_input).to_have_attribute("placeholder", "Search...")
    native_textarea = page.locator("textarea#native-textarea")
    expect(native_textarea).to_be_visible()

    native_input.fill("hello")
    expect(page.locator("#text-value")).to_have_text("hello")

    native_textarea.fill("world")
    expect(page.locator("#area-value")).to_have_text("world")

    assert not page_errors, f"Frontend raised unexpected errors: {page_errors}"
