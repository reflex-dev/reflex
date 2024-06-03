"""Integration tests for deploy_url."""

from __future__ import annotations

from typing import Generator

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from reflex.testing import AppHarness


def DeployUrlSample() -> None:
    """Sample app for testing config deploy_url is correct (in tests)."""
    import reflex as rx

    class State(rx.State):
        def goto_self(self):
            return rx.redirect(rx.config.get_config().deploy_url)  # type: ignore

    def index():
        return rx.fragment(
            rx.button("GOTO SELF", on_click=State.goto_self, id="goto_self")
        )

    app = rx.App(state=rx.State)
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
        app_source=DeployUrlSample,  # type: ignore
    ) as harness:
        yield harness


@pytest.fixture()
def driver(deploy_url_sample: AppHarness) -> Generator[WebDriver, None, None]:
    """WebDriver fixture for testing deploy_url.

    Args:
        deploy_url_sample: AppHarness fixture for testing deploy_url.

    Yields:
        WebDriver: A WebDriver instance.
    """
    assert deploy_url_sample.app_instance is not None, "app is not running"
    driver = deploy_url_sample.frontend()
    try:
        yield driver
    finally:
        driver.quit()


def test_deploy_url(deploy_url_sample: AppHarness, driver: WebDriver) -> None:
    """Test deploy_url is correct.

    Args:
        deploy_url_sample: AppHarness fixture for testing deploy_url.
        driver: WebDriver fixture for testing deploy_url.
    """
    import reflex as rx

    deploy_url = rx.config.get_config().deploy_url
    assert deploy_url is not None
    assert deploy_url != "http://localhost:3000"
    assert deploy_url == deploy_url_sample.frontend_url
    driver.get(deploy_url)
    assert driver.current_url == deploy_url + "/"


def test_deploy_url_in_app(deploy_url_sample: AppHarness, driver: WebDriver) -> None:
    """Test deploy_url is correct in app.

    Args:
        deploy_url_sample: AppHarness fixture for testing deploy_url.
        driver: WebDriver fixture for testing deploy_url.
    """
    driver.implicitly_wait(10)
    driver.find_element(By.ID, "goto_self").click()

    WebDriverWait(driver, 10).until(
        lambda driver: driver.current_url == f"{deploy_url_sample.frontend_url}/"
    )
