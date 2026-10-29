"""Integration tests for compiler-generated experimental memos."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def AutoMemoAcrossPagesApp():
    """Reflex app that shares one stateful subtree across two pages."""
    import reflex as rx

    def shared_counter() -> rx.Component:
        return rx.text(rx.State.router.page.raw_path, id="shared-value")

    def index() -> rx.Component:
        return rx.vstack(
            shared_counter(),
            rx.link("Other", href="/other", id="to-other"),
        )

    def other() -> rx.Component:
        return rx.vstack(
            shared_counter(),
            rx.link("Home", href="/", id="to-home"),
        )

    app = rx.App()
    app.add_page(index)
    app.add_page(other, route="/other")


@pytest.fixture
def auto_memo_app(tmp_path) -> Generator[AppHarness, None, None]:
    """Start the shared-component app.

    Yields:
        The running app harness.
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=AutoMemoAcrossPagesApp,
    ) as harness:
        yield harness


def test_auto_memo_shared_across_pages(auto_memo_app: AppHarness, page: Page):
    """A shared stateful subtree renders correctly on both pages."""
    assert auto_memo_app.app_instance is not None, "app is not running"

    web_sources = "\n".join(
        path.read_text() for path in (auto_memo_app.app_path / ".web").rglob("*.jsx")
    )
    assert "$/app_components" in web_sources
    assert "$/utils/stateful_components" not in web_sources

    assert auto_memo_app.frontend_url is not None
    page.goto(auto_memo_app.frontend_url)
    expect(page.locator("#shared-value")).to_have_text("/")

    page.locator("#to-other").click()
    expect(page.locator("#shared-value")).to_have_text("/other")
