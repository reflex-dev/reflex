"""Test shared state imports from a reusable module."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def SharedStateApp():
    """Create an app using a state class from a reusable module."""
    import reflex as rx
    from tests.integration.shared.state import SharedState

    class State(SharedState):
        pass

    def index() -> rx.Component:
        return rx.vstack(rx.text("Shared state loaded", id="shared-state"))

    app = rx.App()
    app.add_page(index)


@pytest.fixture
def shared_state(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start the app that imports a shared state class.

    Yields:
        The running app harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("shared_state"),
        app_source=SharedStateApp,
    ) as harness:
        yield harness


def test_shared_state(shared_state: AppHarness, page: Page) -> None:
    """The app can import a state class from a reusable module."""
    assert shared_state.app_instance is not None, "app is not running"
    assert shared_state.frontend_url is not None
    page.goto(shared_state.frontend_url)
    expect(page.locator("#shared-state")).to_have_text("Shared state loaded")
