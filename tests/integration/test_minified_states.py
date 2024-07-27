"""Integration tests for minified state names."""

from __future__ import annotations

import time
from typing import Generator, Type

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from reflex.testing import AppHarness


def TestApp():
    """A test app for minified state names."""
    import reflex as rx

    class TestAppState(rx.State):
        """State for the TestApp app."""

        pass

    app = rx.App()

    @app.add_page
    def index():
        return rx.vstack(
            rx.input(
                value=TestAppState.router.session.client_token,
                is_read_only=True,
                id="token",
            ),
        )


@pytest.fixture(scope="module")
def test_app(
    app_harness_env: Type[AppHarness], tmp_path_factory: pytest.TempPathFactory
) -> Generator[AppHarness, None, None]:
    """Start TestApp app at tmp_path via AppHarness.

    Args:
        app_harness_env: either AppHarness (dev) or AppHarnessProd (prod)
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance

    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("test_app"),
        app_name=f"testapp_{app_harness_env.__name__.lower()}",
        app_source=TestApp,  # type: ignore
    ) as harness:
        yield harness


@pytest.fixture
def driver(test_app: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the test_app app.

    Args:
        test_app: harness for TestApp app

    Yields:
        WebDriver instance.

    """
    assert test_app.app_instance is not None, "app is not running"
    driver = test_app.frontend()
    try:
        yield driver
    finally:
        driver.quit()


def test_minified_states(
    test_app: AppHarness,
    driver: WebDriver,
) -> None:
    """Test minified state names.

    Args:
        test_app: harness for TestApp
        driver: WebDriver instance.

    """
    assert test_app.app_instance is not None, "app is not running"

    # get a reference to the connected client
    token_input = driver.find_element(By.ID, "token")
    assert token_input

    # wait for the backend connection to send the token
    token = test_app.poll_for_value(token_input)
    assert token
