"""Integration test for adding an overlay component from rxconfig."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def ExtraOverlay():
    import reflex as rx

    def index():
        return rx.vstack(
            rx.el.input(
                id="token",
                value=rx.State.router.session.client_token,
                is_read_only=True,
            ),
            rx.text("Hello World"),
        )

    app = rx.App()
    rx.config.get_config().extra_overlay_function = "reflex_components_radix.button"
    app.add_page(index)


@pytest.fixture(scope="module")
def extra_overlay(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start the extra-overlay app.

    Yields:
        The running app harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("extra_overlay"),
        app_source=ExtraOverlay,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_extra_overlay(extra_overlay: AppHarness, page: Page) -> None:
    """The configured overlay renders its button without a label."""
    assert extra_overlay.frontend_url is not None
    page.goto(extra_overlay.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")
    expect(page.get_by_text("Hello World", exact=True)).to_be_visible()

    button = page.get_by_role("button")
    expect(button).to_have_count(1)
    expect(button).to_have_text("")
