"""Integration tests for the Moment component."""

import re
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def MomentApp():
    """Create an app that exercises the react-moment 2.x prop changes."""
    import reflex as rx

    app = rx.App()

    class State(rx.State):
        """State used to wait for the browser connection before asserting output."""

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


def test_moment_2_props_render(moment_app: AppHarness, page: Page) -> None:
    """Changed react-moment 2.x props should render without a client error."""
    assert moment_app.frontend_url is not None
    page.goto(moment_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")
    expect(page.locator("#moment")).to_have_text("2026-08-30")
    expect(page.locator("#moment-duration")).to_have_text("30 mins")


def test_moment_locales_are_isolated(moment_app: AppHarness, page: Page) -> None:
    """Keep default moments in English across locales, navigation, and reload."""
    assert moment_app.frontend_url is not None
    page.goto(moment_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    expect(page.locator("#moment-default-locale")).to_have_text(
        "Thursday 14 March 2024"
    )
    expect(page.locator("#moment-french")).to_have_text("jeudi 14 mars 2024")
    expect(page.locator("#moment-provider-locale")).to_have_text("jeudi 14 mars 2024")
    expect(page.locator("#moment-provider-memo-locale")).to_have_text(
        "jeudi 14 mars 2024"
    )

    page.locator("#plain-link").click()
    expect(page.locator("#plain-date")).to_have_text("Thursday 14 March 2024")
    expect(page.locator("#plain-relative")).to_have_text(re.compile(r"ago$"))
    page.locator("#home-link").click()
    expect(page.locator("#moment-default-locale")).to_have_text(
        "Thursday 14 March 2024"
    )
    page.reload()
    expect(page.locator("#moment-default-locale")).to_have_text(
        "Thursday 14 March 2024"
    )


def test_moment_provider_locale_does_not_leak(
    moment_app: AppHarness, page: Page
) -> None:
    """A provider locale stays scoped across client-side navigation."""
    assert moment_app.frontend_url is not None
    page.goto(f"{moment_app.frontend_url.rstrip('/')}/plain")
    expect(page.locator("#plain-date")).to_have_text("Thursday 14 March 2024")
    page.locator("#provider-link").click()
    expect(page.locator("#moment-provider-memo-locale")).to_have_text(
        "jeudi 14 mars 2024"
    )
    page.locator("#provider-plain-link").click()
    expect(page.locator("#plain-date")).to_have_text("Thursday 14 March 2024")
    expect(page.locator("#plain-relative")).to_have_text(re.compile(r"ago$"))
