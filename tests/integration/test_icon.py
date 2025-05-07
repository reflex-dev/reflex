"""Integration tests for the Icon component."""

from collections.abc import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.components.lucide.icon import LUCIDE_ICON_LIST
from reflex.testing import AppHarness
from tests.integration.test_dynamic_components import poll_for_result


def Icons():
    import reflex as rx
    from reflex.components.lucide.icon import LUCIDE_ICON_LIST

    app = rx.App()

    class State(rx.State):
        pass

    @app.add_page
    def index():
        return rx.vstack(
            rx.el.input(
                custom_attrs={
                    "id": "token",
                },
                value=State.router.session.client_token,
                is_read_only=True,
            ),
            *[
                rx.el.div(
                    rx.icon(icon_name),
                    id=icon_name,
                )
                for icon_name in LUCIDE_ICON_LIST
            ],
        )


@pytest.fixture(scope="module")
def icons(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Start Icons app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture

    Yields:
        running AppHarness instance
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("icons"),
        app_source=Icons,
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.fixture
def driver(icons: AppHarness):
    """Get an instance of the browser open to the dynamic components app.

    Args:
        icons: AppHarness for the dynamic components

    Yields:
        WebDriver instance.
    """
    driver = icons.frontend()
    try:
        token_input = poll_for_result(
            lambda: driver.find_element(By.ID, "token"), max_attempts=30
        )
        assert token_input
        # wait for the backend connection to send the token
        token = icons.poll_for_value(token_input)
        assert token is not None

        yield driver
    finally:
        driver.quit()


def test_icons(driver, icons: AppHarness):
    """Test that the var operations produce the right results.

    Args:
        driver: selenium WebDriver open to the app
        icons: AppHarness for the dynamic components
    """
    for icon_name in LUCIDE_ICON_LIST:
        icon = poll_for_result(
            lambda icon_name=icon_name: driver.find_element(By.ID, icon_name)
        )
        assert icon
