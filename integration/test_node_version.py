"""Test for latest node version being able to run reflex."""

from __future__ import annotations

from typing import Any, Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def TestNodeVersionApp():
    """A test app for node latest version."""
    import reflex as rx
    from reflex.utils.prerequisites import get_node_version

    class TestNodeVersionConfig(rx.Config):
        pass

    class TestNodeVersionState(rx.State):
        @rx.var
        def node_version(self) -> str:
            return str(get_node_version())

    app = rx.App()

    @app.add_page
    def index():
        return rx.text("Node Version check ", TestNodeVersionState.node_version)


@pytest.fixture()
def node_version_app(tmp_path) -> Generator[AppHarness, Any, None]:
    """Fixture to start TestNodeVersionApp app at tmp_path via AppHarness.

    Args:
        tmp_path: pytest tmp_path fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=TestNodeVersionApp,  # type: ignore
    ) as harness:
        yield harness


def test_node_version(node_version_app: AppHarness, page: Page):
    """Test for latest node version being able to run reflex.

    Args:
        node_version_app: running AppHarness instance
        page: playwright page instance
    """
    assert node_version_app.frontend_url is not None
    page.goto(node_version_app.frontend_url)
    expect(page.get_by_text("Node Version check 20.17.0")).to_be_visible()