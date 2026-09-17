"""Integration tests for the Moment component."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness

from .utils import poll_for_token


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
def driver(moment_app: AppHarness, page: Page) -> Page:
    """Open the Moment app and wait for hydration.

    Args:
        moment_app: The running app.
        page: Playwright page.

    Returns:
        The hydrated page.
    """
    assert moment_app.frontend_url is not None
    page.goto(moment_app.frontend_url)
    poll_for_token(page)
    return page


def test_moment_2_props_render(driver: Page) -> None:
    """Changed react-moment 2.x props render without a client error."""
    expect(driver.locator("#moment")).to_have_text("2026-08-30")
    expect(driver.locator("#moment-duration")).to_have_text("30 mins")


def test_moment_locales_are_isolated(driver: Page) -> None:
    """Keep default moments in English across locales, navigation and reload.

    Args:
        driver: The hydrated page.
    """
    expect(driver.locator("#moment-default-locale")).to_have_text(
        "Thursday 14 March 2024"
    )
    expect(driver.locator("#moment-french")).to_have_text("jeudi 14 mars 2024")
    driver.locator("#plain-link").click()
    expect(driver.locator("#plain-date")).to_have_text("Thursday 14 March 2024")
    expect(driver.locator("#plain-relative")).to_contain_text("ago")
    driver.locator("#home-link").click()
    expect(driver.locator("#moment-default-locale")).to_have_text(
        "Thursday 14 March 2024"
    )
    driver.reload()
    expect(driver.locator("#moment-default-locale")).to_have_text(
        "Thursday 14 March 2024"
    )
