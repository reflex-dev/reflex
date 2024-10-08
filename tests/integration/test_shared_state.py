"""Test shared state."""

from __future__ import annotations

from typing import Generator

import pytest

from reflex.testing import AppHarness, WebDriver


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


@pytest.fixture
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
        app_source=SharedStateApp,  # type: ignore
    ) as harness:
        yield harness


@pytest.fixture
def driver(shared_state: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the shared_state app.

    Args:
        shared_state: harness for SharedStateApp

    Yields:
        WebDriver instance.

    """
    assert shared_state.app_instance is not None, "app is not running"
    driver = shared_state.frontend()
    try:
        yield driver
    finally:
        driver.quit()


def test_shared_state(
    shared_state: AppHarness,
    driver: WebDriver,
):
    """Test that 2 AppHarness instances can share a state (f.e. from a library).

    Args:
        shared_state: harness for SharedStateApp.
        driver: WebDriver instance.

    """
    assert shared_state.app_instance is not None
