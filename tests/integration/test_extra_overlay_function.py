"""Test case for adding an overlay component defined in the rxconfig."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

from . import utils


def ExtraOverlay():
    import reflex as rx

    def index():
        return rx.vstack(
            rx.el.input(
                id="token",
                value=rx.State.router.session.client_token,
                is_read_only=True,
            ),
            rx.text(
                "Hello World",
            ),
        )

    app = rx.App()
    rx.config.get_config().extra_overlay_function = (
        "reflex_components_radix.themes.components.button"
    )
    app.add_page(index)


@pytest.fixture(scope="module")
def extra_overlay(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start ExtraOverlay app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("extra_overlay"),
        app_source=ExtraOverlay,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_extra_overlay(extra_overlay: AppHarness, page: Page):
    """Test the ExtraOverlay app.

    Args:
        extra_overlay: harness for the ExtraOverlay app.
        page: Playwright Page fixture.
    """
    assert extra_overlay.frontend_url is not None
    page.goto(extra_overlay.frontend_url)

    # wait for the backend connection to send the token
    token = utils.poll_for_token(page)
    assert token is not None

    # Check that the text is displayed.
    text = page.locator("xpath=//*[contains(text(), 'Hello World')]").first
    expect(text).to_have_text("Hello World")

    button = page.locator("button").first
    expect(button).to_be_visible()
    expect(button).to_have_text("")
