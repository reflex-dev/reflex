"""Integration test for @radix-ui/themes integration."""

from __future__ import annotations

import time
from typing import Generator

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from reflex.testing import DEFAULT_TIMEOUT, AppHarness, WebDriver


def RadixThemesApp():
    """App using radix-themes components."""
    import reflex as rx
    import reflex.components.radix.themes as rdxt

    class State(rx.State):
        v: str = ""
        checked: bool = False

    def index() -> rx.Component:
        return rdxt.flex(
            rdxt.textfield_root(
                rdxt.textfield_slot("🧸"),
                rdxt.textfield_input(id="tf-slotted", value=State.v, on_change=State.set_v),  # type: ignore
            )
        )

    app = rx.App(
        state=rx.State,
        theme=rdxt.theme(rdxt.theme_panel(), accent_color="grass"),
    )
    app.add_page(index)
    app.compile()


@pytest.fixture(scope="session")
def radix_themes_app(
    tmp_path_factory,
) -> Generator[AppHarness, None, None]:
    """Start BackgroundTask app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp(f"radix_themes_app"),
        app_source=RadixThemesApp,  # type: ignore
    ) as harness:
        yield harness


@pytest.fixture
def driver(radix_themes_app: AppHarness) -> Generator[WebDriver, None, None]:
    """Get an instance of the browser open to the radix_themes_app app.

    Args:
        radix_themes_app: harness for BackgroundTask app

    Yields:
        WebDriver instance.
    """
    assert radix_themes_app.app_instance is not None, "app is not running"
    driver = radix_themes_app.frontend()
    try:
        yield driver
    finally:
        driver.quit()


@pytest.fixture()
def token(radix_themes_app: AppHarness, driver: WebDriver) -> str:
    """Get a function that returns the active token.

    Args:
        radix_themes_app: harness for BackgroundTask app.
        driver: WebDriver instance.

    Returns:
        The token for the connected client
    """
    assert radix_themes_app.app_instance is not None
    token_input = driver.find_element(By.ID, "token")
    assert token_input

    # wait for the backend connection to send the token
    token = radix_themes_app.poll_for_value(token_input, timeout=DEFAULT_TIMEOUT * 2)
    assert token is not None

    return token


def test_radix_themes_app(
    radix_themes_app: AppHarness,
    driver: WebDriver,
    token: str,
):
    """Test that background tasks work as expected.

    Args:
        radix_themes_app: harness for BackgroundTask app.
        driver: WebDriver instance.
        token: The token for the connected client.
    """
    assert radix_themes_app.app_instance is not None
