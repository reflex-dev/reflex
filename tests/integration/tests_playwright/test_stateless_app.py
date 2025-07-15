"""Integration tests for a stateless app."""

from collections.abc import Generator

import httpx
import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def StatelessApp():
    """A stateless app that renders a heading."""
    import reflex as rx

    def index():
        return rx.heading("This is a stateless app")

    app = rx.App()
    app.add_page(index)


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
    assert stateless_app.reflex_process is not None
    assert (
        stateless_app.reflex_process.poll() is None
    )  # Ensure the process is still running

    res = httpx.get(f"http://localhost:{stateless_app.backend_port}/_event")
    assert res.status_code == 404

    res2 = httpx.get(f"http://localhost:{stateless_app.backend_port}/ping")
    assert res2.status_code == 200

    page.goto(stateless_app.frontend_url)
    expect(page.get_by_role("heading")).to_have_text("This is a stateless app")
