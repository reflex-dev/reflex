"""Integration tests for links and related components."""

from collections.abc import Generator
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

from .utils import SessionStorage, poll_for_navigation


def NavigationApp():
    """Reflex app with links for navigation."""
    import reflex as rx

    class State(rx.State):
        is_external: bool = True

    app = rx.App()

    @app.add_page
    def index():
        return rx.fragment(
            rx.link("Internal", href="/internal", id="internal"),
            rx.link(
                "External",
                href="/internal",
                is_external=State.is_external,
                id="external",
            ),
            rx.link(
                "External Target", href="/internal", target="_blank", id="external2"
            ),
        )

    @rx.page(route="/internal")
    def internal():
        return rx.text("Internal")


@pytest.fixture(scope="module")
def navigation_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start NavigationApp app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("navigation_app"),
        app_source=NavigationApp,
    ) as harness:
        yield harness


def test_navigation_app(navigation_app: AppHarness, page: Page):
    """Type text after moving cursor. Update text on backend.

    Args:
        navigation_app: harness for NavigationApp app
        page: Playwright page
    """
    assert navigation_app.app_instance is not None, "app is not running"
    assert navigation_app.frontend_url is not None
    page.goto(navigation_app.frontend_url)

    ss = SessionStorage(page)
    assert AppHarness._poll_for(lambda: ss.get("token") is not None), "token not found"

    internal_link = page.locator("#internal")

    with poll_for_navigation(page):
        internal_link.click()
    assert urlsplit(page.url).path == "/internal"
    with poll_for_navigation(page):
        page.go_back()

    external_link = page.locator("#external")
    expect(external_link).to_have_count(1)
    external2_link = page.locator("#external2")

    with page.context.expect_page():
        external_link.click()
    # Expect a new tab to open
    AppHarness.expect(lambda: len(page.context.pages) == 2)

    with page.context.expect_page():
        external2_link.click()
    # Expect another new tab to open
    AppHarness.expect(lambda: len(page.context.pages) == 3)
