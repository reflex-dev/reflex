"""Integration tests for deploy_url."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from playwright.sync_api import Page

from reflex.testing import AppHarness


def DeployUrlSample() -> None:
    """Sample app for testing config deploy_url is correct (in tests)."""
    import reflex as rx

    class State(rx.State):
        @rx.event
        def goto_self(self):
            if (deploy_url := rx.config.get_config().deploy_url) is not None:
                return rx.redirect(deploy_url)
            return None

    def index():
        return rx.fragment(
            rx.button("GOTO SELF", on_click=State.goto_self, id="goto_self")
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def deploy_url_sample(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """AppHarness fixture for testing deploy_url.

    Args:
        tmp_path_factory: pytest fixture for creating temporary directories.

    Yields:
        AppHarness: An AppHarness instance.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("deploy_url_sample"),
        app_source=DeployUrlSample,
    ) as harness:
        yield harness


def test_deploy_url(deploy_url_sample: AppHarness, page: Page) -> None:
    """Test deploy_url is correct.

    Args:
        deploy_url_sample: AppHarness fixture for testing deploy_url.
        page: Playwright page instance.
    """
    import reflex as rx

    deploy_url = rx.config.get_config().deploy_url
    assert deploy_url is not None
    assert deploy_url != "http://localhost:3000"
    assert deploy_url == deploy_url_sample.frontend_url
    page.goto(deploy_url)
    assert page.url.removesuffix("/") == deploy_url.removesuffix("/")


def test_deploy_url_in_app(deploy_url_sample: AppHarness, page: Page) -> None:
    """Test deploy_url is correct in app.

    Args:
        deploy_url_sample: AppHarness fixture for testing deploy_url.
        page: Playwright page instance.
    """
    assert deploy_url_sample.frontend_url is not None
    target = deploy_url_sample.frontend_url.removesuffix("/")
    page.goto(deploy_url_sample.frontend_url)
    page.locator("#goto_self").click()

    AppHarness.expect(lambda: page.url.removesuffix("/") == target, timeout=10)
