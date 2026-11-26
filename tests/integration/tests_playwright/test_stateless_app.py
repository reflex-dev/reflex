"""Integration tests for a stateless app."""

from collections.abc import Generator

import httpx2
import pytest
from playwright.sync_api import Page, expect
from reflex_base.config import get_config
from reflex_base.constants import Endpoint

from reflex.testing import AppHarness


def StatelessApp():
    """A stateless app that renders a heading and a page with its own stylesheet."""
    from pathlib import Path

    import reflex as rx

    def index():
        return rx.fragment(
            rx.heading("This is a stateless app"),
            rx.el.p("Index", class_name="page-styled", id="index-paragraph"),
            rx.link("Styled", href="/styled", id="styled-link"),
        )

    def styled():
        return rx.fragment(
            rx.el.p("Styled", class_name="page-styled", id="styled-paragraph"),
            rx.link("Home", href="/", id="home-link"),
        )

    assets = Path.cwd() / "assets"
    assets.mkdir(exist_ok=True)
    (assets / "app.css").write_text(".page-styled { color: rgb(255, 0, 0); }")
    (assets / "styled.css").write_text(".page-styled { color: rgb(0, 0, 255); }")
    app = rx.App(enable_state=False, stylesheets=["/app.css"])
    app.add_page(index)
    app.add_page(styled, route="/styled", stylesheets=["/styled.css"])


@pytest.fixture(scope="module")
def stateless_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Create a stateless app AppHarness.

    Args:
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        AppHarness: A harness for testing the stateless app.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("stateless_app"),
        app_source=StatelessApp,
    ) as harness:
        yield harness


def test_statelessness(stateless_app: AppHarness, page: Page):
    """Test that the stateless app renders a heading but backend/_event is not mounted.

    Args:
        stateless_app: A harness for testing the stateless app.
        page: A Playwright page.
    """
    assert stateless_app.frontend_url is not None
    assert stateless_app.backend is not None
    assert stateless_app.backend.started

    config = get_config()
    res = httpx2.get(config.api_url + config.prepend_backend_path(str(Endpoint.EVENT)))
    assert res.status_code == 404

    res2 = httpx2.get(Endpoint.PING.get_url())
    assert res2.status_code == 200

    page.goto(stateless_app.frontend_url)
    expect(page.get_by_role("heading")).to_have_text("This is a stateless app")


def test_page_stylesheets(stateless_app: AppHarness, page: Page):
    """A page's stylesheet applies after the app's, only while the page is shown.

    The links navigate client-side, so React Router itself has to add the
    stylesheet and remove it again: a document reload would drop it anyway.

    Args:
        stateless_app: A harness for testing the stateless app.
        page: A Playwright page.
    """
    assert stateless_app.frontend_url is not None
    page.goto(stateless_app.frontend_url)
    expect(page.locator("#index-paragraph")).to_have_css("color", "rgb(255, 0, 0)")
    page.evaluate("() => { window.__same_document = true; }")

    page.locator("#styled-link").click()
    expect(page.locator("#styled-paragraph")).to_have_css("color", "rgb(0, 0, 255)")

    page.locator("#home-link").click()
    expect(page.locator("#index-paragraph")).to_have_css("color", "rgb(255, 0, 0)")
    assert page.evaluate("() => window.__same_document") is True

    page.goto(stateless_app.frontend_url.rstrip("/") + "/styled")
    expect(page.locator("#styled-paragraph")).to_have_css("color", "rgb(0, 0, 255)")
