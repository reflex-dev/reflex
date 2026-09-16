"""Integration tests for links and related components."""

from collections.abc import Generator
from urllib.parse import urlsplit

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness

from .utils import SessionStorage, click_element, poll_for_navigation


def NavigationApp():
    """Reflex app with links for navigation."""
    import reflex as rx

    class State(rx.State):
        is_external: bool = True

    app = rx.App()

    @app.add_page
    def index():
        return rx.fragment(
            rx.link("Internal", href="/internal", id="internal"),
            rx.link(
                "External",
                href="/internal",
                is_external=State.is_external,
                id="external",
            ),
            rx.link(
                "External Target", href="/internal", target="_blank", id="external2"
            ),
        )

    @rx.page(route="/internal")
    def internal():
        return rx.text("Internal")


@pytest.fixture
def navigation_app(tmp_path) -> Generator[AppHarness, None, None]:
    """Start NavigationApp app at tmp_path via AppHarness.

    Args:
        tmp_path: pytest tmp_path fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=NavigationApp,
    ) as harness:
        yield harness


def test_navigation_app(navigation_app: AppHarness):
    """Type text after moving cursor. Update text on backend.

    Args:
        navigation_app: harness for NavigationApp app
    """
    assert navigation_app.app_instance is not None, "app is not running"
    driver = navigation_app.frontend()

    ss = SessionStorage(driver)
    assert AppHarness._poll_for(lambda: ss.get("token") is not None), "token not found"

    with poll_for_navigation(driver):
        click_element(driver, By.ID, "internal")
    assert urlsplit(driver.current_url).path == "/internal"
    with poll_for_navigation(driver):
        driver.back()

    click_element(driver, By.ID, "external")
    # Expect a new tab to open
    AppHarness.expect(lambda: len(driver.window_handles) == 2)

    # Switch back to the main tab
    driver.switch_to.window(driver.window_handles[0])

    click_element(driver, By.ID, "external2")
    # Expect another new tab to open
    AppHarness.expect(lambda: len(driver.window_handles) == 3)
