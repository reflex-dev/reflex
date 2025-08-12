"""Integration tests for the Icon component."""

from collections.abc import Generator

import pytest
from selenium.webdriver.common.by import By

from reflex.components.lucide.icon import LUCIDE_ICON_LIST
from reflex.testing import AppHarness, WebDriver


def Icons():
    import reflex as rx
    from reflex.components.lucide.icon import LUCIDE_ICON_LIST

    app = rx.App()

    class State(rx.State):
        """State for the Icons app."""

        dynamic_icon: str = "airplay"

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
            rx.el.div(
                rx.icon(State.dynamic_icon),
                id="dynamic_icon",
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
def icons(
    tmp_path_factory, app_harness_env: type[AppHarness]
) -> Generator[AppHarness, None, None]:
    """Start Icons app at tmp_path via AppHarness.

    Args:
        tmp_path_factory: pytest tmp_path_factory fixture
        app_harness_env: The AppHarness environment to use

    Yields:
        running AppHarness instance
    """
    with app_harness_env.create(
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
        token_input = AppHarness.poll_for_or_raise_timeout(
            lambda: driver.find_element(By.ID, "token")
        )
        # wait for the backend connection to send the token
        token = icons.poll_for_value(token_input)
        assert token is not None

        yield driver
    finally:
        driver.quit()


def test_icons(driver: WebDriver, icons: AppHarness):
    """Test that the var operations produce the right results.

    Args:
        driver: selenium WebDriver open to the app
        icons: AppHarness for the dynamic components
    """
    for icon_name in [*LUCIDE_ICON_LIST, "dynamic_icon"]:
        AppHarness.expect(
            lambda icon_name=icon_name: driver.find_element(
                By.ID, icon_name
            ).find_element(By.TAG_NAME, "svg")
        )
