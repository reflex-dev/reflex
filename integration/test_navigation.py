"""Integration tests for links and related components."""

from typing import Generator
from urllib.parse import urlsplit

import pytest
from selenium.webdriver.common.by import By

from reflex.testing import AppHarness

from .utils import SessionStorage, poll_for_navigation


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


@pytest.fixture()
def navigation_app(tmp_path) -> Generator[AppHarness, None, None]:
    """Start NavigationApp app at tmp_path via AppHarness.

    Args:
        tmp_path: pytest tmp_path fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path,
        app_source=NavigationApp,  # type: ignore
    ) as harness:
        yield harness


@pytest.mark.asyncio
async def test_navigation_app(navigation_app: AppHarness):
    """Type text after moving cursor. Update text on backend.

    Args:
        navigation_app: harness for NavigationApp app
    """
    assert navigation_app.app_instance is not None, "app is not running"
    driver = navigation_app.frontend()

    ss = SessionStorage(driver)
    assert AppHarness._poll_for(lambda: ss.get("token") is not None), "token not found"

    internal_link = driver.find_element(By.ID, "internal")

    with poll_for_navigation(driver):
        internal_link.click()
    assert urlsplit(driver.current_url).path == f"/internal/"
    with poll_for_navigation(driver):
        driver.back()

    external_link = driver.find_element(By.ID, "external")
    external2_link = driver.find_element(By.ID, "external2")

    external_link.click()
    # Expect a new tab to open
    assert AppHarness._poll_for(lambda: len(driver.window_handles) == 2)

    # Switch back to the main tab
    driver.switch_to.window(driver.window_handles[0])

    external2_link.click()
    # Expect another new tab to open
    assert AppHarness._poll_for(lambda: len(driver.window_handles) == 3)
