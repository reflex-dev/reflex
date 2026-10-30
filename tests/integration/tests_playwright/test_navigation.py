"""Integration tests for links and related components."""

import re
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


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


@pytest.fixture
def navigation_app(tmp_path) -> Generator[AppHarness, None, None]:
    """Start the navigation app.

    Yields:
        The running app harness.
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=NavigationApp,
    ) as harness:
        yield harness


def test_navigation_app(navigation_app: AppHarness, page: Page) -> None:
    """Internal links navigate in place; external links open new pages."""
    assert navigation_app.frontend_url is not None
    page.goto(navigation_app.frontend_url)

    page.locator("#internal").click()
    expect(page).to_have_url(re.compile(r".*/internal/?$"))
    expect(page.get_by_text("Internal", exact=True)).to_be_visible()

    page.go_back()
    expect(page).to_have_url(re.compile(r"^https?://[^/]+/?$"))

    with page.expect_popup() as external_popup:
        page.locator("#external").click()
    expect(external_popup.value).to_have_url(re.compile(r".*/internal/?$"))
    external_popup.value.close()

    with page.expect_popup() as target_popup:
        page.locator("#external2").click()
    expect(target_popup.value).to_have_url(re.compile(r".*/internal/?$"))
