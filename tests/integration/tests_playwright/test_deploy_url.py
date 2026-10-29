"""Playwright integration tests for deploy_url."""

import re
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

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
    """Start the deploy_url sample app.

    Yields:
        The running app harness.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("deploy_url_sample"),
        app_source=DeployUrlSample,
    ) as harness:
        yield harness


def test_deploy_url(deploy_url_sample: AppHarness, page: Page) -> None:
    """The configured deploy URL points to the running frontend."""
    import reflex as rx

    deploy_url = rx.config.get_config().deploy_url
    assert deploy_url is not None
    assert deploy_url != "http://localhost:3000"
    assert deploy_url == deploy_url_sample.frontend_url

    page.goto(deploy_url)
    expect(page).to_have_url(re.compile(rf"^{re.escape(deploy_url.rstrip('/'))}/?$"))


def test_deploy_url_in_app(deploy_url_sample: AppHarness, page: Page) -> None:
    """The app's self-redirect returns to its configured deploy URL."""
    deploy_url = deploy_url_sample.frontend_url
    assert deploy_url is not None

    page.goto(deploy_url)
    button = page.get_by_role("button", name="GOTO SELF")
    expect(button).to_be_visible()
    button.click()

    expect(page).to_have_url(re.compile(rf"^{re.escape(deploy_url.rstrip('/'))}/?$"))
