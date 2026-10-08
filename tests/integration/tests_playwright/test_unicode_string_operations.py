"""Browser tests for Unicode-aware StringVar indexing and slicing."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def UnicodeStringApp():
    """Render StringVar code-point operations for an astral character."""
    import reflex as rx

    class UnicodeState(rx.State):
        value: str = "a\U0001f600b"

    app = rx.App(_state=UnicodeState)

    @app.add_page
    def index():
        return rx.vstack(
            rx.text(
                UnicodeState.value.length(),  # pyright: ignore[reportAttributeAccessIssue]
                id="length",
            ),
            rx.text(UnicodeState.value[::-1], id="reverse"),
            rx.text(UnicodeState.value[1], id="character"),
        )


@pytest.fixture(scope="module")
def unicode_string_app(
    tmp_path_factory, app_harness_env
) -> Generator[AppHarness, None, None]:
    """Start the Unicode string app in dev and production harnesses.

    Yields:
        The running app harness.
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("unicode_string_app"),
        app_source=UnicodeStringApp,
    ) as harness:
        yield harness


def test_unicode_string_operations_preserve_code_points(
    unicode_string_app: AppHarness, page: Page
):
    """Length, reverse slicing, and indexing keep surrogate pairs intact."""
    assert unicode_string_app.frontend_url is not None
    page_errors: list[str] = []
    console_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.on(
        "console",
        lambda message: (
            console_errors.append(message.text) if message.type == "error" else None
        ),
    )

    page.goto(unicode_string_app.frontend_url)

    expect(page.locator("#length")).to_have_text("3")
    expect(page.locator("#reverse")).to_have_text("b\U0001f600a")
    expect(page.locator("#character")).to_have_text("\U0001f600")
    assert not page_errors
    assert not console_errors
