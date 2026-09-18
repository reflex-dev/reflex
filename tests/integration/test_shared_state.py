"""Test shared state."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from playwright.sync_api import Page

from reflex.testing import AppHarness


def SharedStateApp():
    """Test that shared state works as expected."""
    import reflex as rx
    from tests.integration.shared.state import SharedState

    class State(SharedState):
        pass

    def index() -> rx.Component:
        return rx.vstack()

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def shared_state(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start SharedStateApp at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance

    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("shared_state"),
        app_source=SharedStateApp,
    ) as harness:
        yield harness


def test_shared_state(
    shared_state: AppHarness,
    page: Page,
):
    """Test that 2 AppHarness instances can share a state (f.e. from a library).

    Args:
        shared_state: harness for SharedStateApp.
        page: Playwright page instance.

    """
    assert shared_state.app_instance is not None
    assert shared_state.frontend_url is not None
    page.goto(shared_state.frontend_url)
