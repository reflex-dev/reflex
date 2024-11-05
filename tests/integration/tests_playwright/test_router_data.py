import time
from typing import Generator

import pytest
from playwright.sync_api import Page

from reflex.testing import AppHarness


def RouterDataApp():
    """App using router data."""
    import reflex as rx

    app = rx.App(state=rx.State)

    @app.add_page
    def index():
        return rx.text(rx.State.router.session.client_token)


@pytest.fixture()
def router_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start Table app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance

    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("table"),
        app_source=RouterDataApp,  # type: ignore
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


def test_router_data(router_app: AppHarness, page: Page):
    assert router_app.frontend_url is not None

    page.goto(router_app.frontend_url)
    time.sleep(5)
