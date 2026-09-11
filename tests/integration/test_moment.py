"""Integration tests for the Moment component."""

from collections.abc import Generator

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from reflex.testing import AppHarness


def MomentApp():
    """Create an app that exercises the react-moment 2.x prop changes."""
    import reflex as rx

    app = rx.App()

    class State(rx.State):
        """State used to wait for the browser connection before asserting output."""

    @app.add_page
    def index():
        return rx.vstack(
            rx.el.input(
                id="token",
                value=State.router.session.client_token,
                is_read_only=True,
            ),
            rx.moment(
                "2026-08-30",
                format="YYYY-MM-DD",
                parse=["YYYY-MM-DD"],
                id="moment",
            ),
            rx.moment(
                date="2026-08-30T00:30:00",
                duration="2026-08-30T00:00:00",
                format="h [hrs] m [min]",
                trim="large",
                id="moment-duration",
            ),
            rx.moment(
                "2024-03-14T15:09:26",
                format="dddd D MMMM YYYY",
                id="moment-default-locale",
            ),
            rx.moment(
                "2024-03-14T15:09:26",
                format="dddd D MMMM YYYY",
                locale="fr",
                id="moment-french",
            ),
            rx.link("Plain page", href="/plain", id="plain-link"),
        )

    def plain():
        """Render moments after another route has loaded a foreign locale.

        Returns:
            The page used to check date and relative-time locale isolation.
        """
        return rx.vstack(
            rx.moment(
                "2024-03-14T15:09:26",
                format="dddd D MMMM YYYY",
                id="plain-date",
            ),
            rx.moment("2020-01-01", from_now=True, id="plain-relative"),
            rx.link("Home", href="/", id="home-link"),
        )

    app.add_page(plain, route="/plain")


@pytest.fixture(scope="module")
def moment_app(
    tmp_path_factory, app_harness_env: type[AppHarness]
) -> Generator[AppHarness, None, None]:
    """Start the Moment integration app.

    Yields:
        The running Moment app harness.
    """
    with app_harness_env.create(
        root=tmp_path_factory.mktemp("moment"), app_source=MomentApp
    ) as harness:
        assert harness.app_instance is not None, "app is not running"
        yield harness


@pytest.fixture
def driver(moment_app: AppHarness) -> Generator[WebDriver, None, None]:
    """Open the Moment integration app in a browser.

    Yields:
        The browser driver connected to the Moment app.
    """
    driver = moment_app.frontend()
    try:
        token = AppHarness.poll_for_or_raise_timeout(
            lambda: driver.find_element(By.ID, "token")
        )
        AppHarness.poll_for_or_raise_timeout(lambda: token.get_attribute("value"))
        yield driver
    finally:
        driver.quit()


def test_moment_2_props_render(driver: WebDriver) -> None:
    """Changed react-moment 2.x props should render without a client error."""
    moment = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "moment")
    )
    AppHarness.expect(lambda: moment.text == "2026-08-30")
    moment_duration = AppHarness.poll_for_or_raise_timeout(
        lambda: driver.find_element(By.ID, "moment-duration")
    )
    AppHarness.expect(lambda: moment_duration.text == "30 mins")


def test_moment_locales_are_isolated(driver: WebDriver) -> None:
    """Keep default moments in English across sibling locales, navigation and reload.

    Args:
        driver: The browser connected to the Moment app.
    """
    AppHarness.expect(
        lambda: (
            driver.find_element(By.ID, "moment-default-locale").text
            == "Thursday 14 March 2024"
        )
    )
    assert driver.find_element(By.ID, "moment-french").text == "jeudi 14 mars 2024"
    driver.find_element(By.ID, "plain-link").click()
    AppHarness.expect(
        lambda: (
            driver.find_element(By.ID, "plain-date").text == "Thursday 14 March 2024"
        )
    )
    AppHarness.expect(
        lambda: driver.find_element(By.ID, "plain-relative").text.endswith("ago")
    )
    driver.find_element(By.ID, "home-link").click()
    AppHarness.expect(
        lambda: (
            driver.find_element(By.ID, "moment-default-locale").text
            == "Thursday 14 March 2024"
        )
    )
    driver.refresh()
    AppHarness.expect(
        lambda: (
            driver.find_element(By.ID, "moment-default-locale").text
            == "Thursday 14 March 2024"
        )
    )
