"""Test case for adding an overlay component defined in the rxconfig."""

from collections.abc import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness, WebDriver


def ExtraOverlay():
    import reflex as rx

    def index():
        return rx.vstack(
            rx.el.input(
                id="token",
                value=rx.State.router.session.client_token,
                is_read_only=True,
            ),
            rx.text(
                "Hello World",
            ),
        )

    app = rx.App()
    rx.config.get_config().extra_overlay_function = (
        "reflex.components.radix.themes.components.button"
    )
    app.add_page(index)


@pytest.fixture(scope="module")
def extra_overlay(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start ExtraOverlay app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("extra_overlay"),
        app_source=ExtraOverlay,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.fixture
def driver(extra_overlay: AppHarness):
    """Get an instance of the browser open to the extra overlay app.

    Args:
        extra_overlay: harness for the ExtraOverlay app.

    Yields:
        WebDriver instance.
    """
    driver = extra_overlay.frontend()
    try:
        token_input = AppHarness.poll_for_or_raise_timeout(
            lambda: driver.find_element(By.ID, "token")
        )
        # wait for the backend connection to send the token
        token = extra_overlay.poll_for_value(token_input)
        assert token is not None

        yield driver
    finally:
        driver.quit()


def test_extra_overlay(driver: WebDriver, extra_overlay: AppHarness):
    """Test the ExtraOverlay app.

    Args:
        driver: WebDriver instance.
        extra_overlay: harness for the ExtraOverlay app.
    """
    # Check that the text is displayed.
    text = driver.find_element(By.XPATH, "//*[contains(text(), 'Hello World')]")
    assert text
    assert text.text == "Hello World"

    button = driver.find_element(By.TAG_NAME, "button")
    assert button
    assert not button.text
