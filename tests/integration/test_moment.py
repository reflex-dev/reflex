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

        locale: str = "fr"

    @rx.memo
    def memoized_provider_moment():
        return rx.moment(
            "2024-03-14T15:09:26",
            format="dddd D MMMM YYYY",
            id="moment-provider-memo-locale",
        )

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
            rx.moment(
                "2024-03-14T15:09:26",
                format="dddd D MMMM YYYY",
                locale=State.locale,
                id="moment-reactive-locale",
            ),
            rx.moment_provider(
                rx.box(
                    rx.moment(
                        "2024-03-14T15:09:26",
                        format="dddd D MMMM YYYY",
                        id="moment-provider-locale",
                    )
                ),
                memoized_provider_moment(),
                locale="fr",
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
            rx.link("Provider page", href="/provider", id="provider-link"),
        )

    def provider():
        """Render a provider locale whose moments compile outside the page module.

        Returns:
            The page that loads a foreign locale only through a provider.
        """
        return rx.vstack(
            rx.moment_provider(memoized_provider_moment(), locale="fr"),
            rx.link("Plain page", href="/plain", id="provider-plain-link"),
        )

    app.add_page(plain, route="/plain")
    app.add_page(provider, route="/provider")


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
    AppHarness.expect(
        lambda: driver.find_element(By.ID, "moment-french").text == "jeudi 14 mars 2024"
    )
    AppHarness.expect(
        lambda: (
            driver.find_element(By.ID, "moment-reactive-locale").text
            == "jeudi 14 mars 2024"
        )
    )
    AppHarness.expect(
        lambda: (
            driver.find_element(By.ID, "moment-provider-locale").text
            == "jeudi 14 mars 2024"
        )
    )
    AppHarness.expect(
        lambda: (
            driver.find_element(By.ID, "moment-provider-memo-locale").text
            == "jeudi 14 mars 2024"
        )
    )
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


def test_moment_provider_locale_does_not_leak(
    moment_app: AppHarness, driver: WebDriver
) -> None:
    """A provider locale stays inside the provider across client-side navigation.

    The page load starts on a route that has not loaded the French locale module.

    Args:
        moment_app: The running Moment app harness.
        driver: The browser connected to the Moment app.
    """
    assert moment_app.frontend_url is not None
    driver.get(moment_app.frontend_url.rstrip("/") + "/plain")
    AppHarness.expect(
        lambda: (
            driver.find_element(By.ID, "plain-date").text == "Thursday 14 March 2024"
        )
    )
    driver.find_element(By.ID, "provider-link").click()
    AppHarness.expect(
        lambda: (
            driver.find_element(By.ID, "moment-provider-memo-locale").text
            == "jeudi 14 mars 2024"
        )
    )
    driver.find_element(By.ID, "provider-plain-link").click()
    AppHarness.expect(
        lambda: (
            driver.find_element(By.ID, "plain-date").text == "Thursday 14 March 2024"
        )
    )
    AppHarness.expect(
        lambda: driver.find_element(By.ID, "plain-relative").text.endswith("ago")
    )
