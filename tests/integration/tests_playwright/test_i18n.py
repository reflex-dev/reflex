"""Integration tests for i18n: static (rx.t) and dynamic (gettext) content."""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def I18nApp():
    """App exercising static and dynamic translation."""
    import datetime
    from pathlib import Path

    import reflex as rx
    from reflex.i18n import format_number
    from reflex.i18n import gettext as _

    po_header = (
        'msgid ""\n'
        'msgstr ""\n'
        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
    )
    de_po = po_header + (
        'msgid "Hello"\n'
        'msgstr "Hallo"\n\n'
        'msgid "{count} item"\n'
        'msgid_plural "{count} items"\n'
        'msgstr[0] "{count} Artikel"\n'
        'msgstr[1] "{count} Artikel"\n\n'
        'msgid "Welcome"\n'
        'msgstr "Willkommen"\n'
    )

    # Written at compile time (cwd is the app root here) so the compiler and
    # backend both find it.
    locales = Path("locales")
    locales.mkdir(exist_ok=True)
    (locales / "de.po").write_text(de_po, encoding="utf-8")
    (locales / "en.po").write_text(po_header, encoding="utf-8")

    class PageState(rx.State):
        count: int = 1
        amount: float = 1234.5
        # A date-only and a time-only value: client-side formatting must parse
        # these without a UTC day-shift or an "Invalid Date".
        day: datetime.date = datetime.date(2026, 7, 18)
        meeting: datetime.time = datetime.time(14, 30, 0)
        # Set at emit time by an event handler; translated server-side into
        # the active locale via gettext.
        message: str = ""

        @rx.event
        def increment(self):
            self.count += 1

        @rx.event
        def greet(self):
            self.message = _("Welcome")

        @rx.var
        def computed_greeting(self) -> str:
            # No explicit locale reference: auto-detection injects the
            # dependency on the active locale so this recomputes on switch.
            return _("Welcome")

        @rx.var
        def server_number(self) -> str:
            # Server-side Babel formatting; auto-reformats on locale switch.
            return format_number(self.amount, min_fraction_digits=2)

    def index():
        return rx.box(
            rx.input(
                value=PageState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.text(rx.t("Hello"), id="static-hello"),
            rx.text(
                rx.t("{count} item", plural="{count} items", count=PageState.count),
                id="static-count",
            ),
            rx.text(PageState.message, id="dynamic-message"),
            rx.text(PageState.computed_greeting, id="computed-greeting"),
            rx.text(
                rx.i18n.number(PageState.amount, min_fraction_digits=2),
                id="client-number",
            ),
            rx.text(PageState.server_number, id="server-number"),
            rx.text(rx.i18n.date(PageState.day, length="medium"), id="client-date"),
            rx.text(rx.i18n.time(PageState.meeting, length="short"), id="client-time"),
            rx.button("inc", on_click=PageState.increment, id="inc"),
            rx.button("greet", on_click=PageState.greet, id="greet"),
            rx.button("de", on_click=rx.i18n.set_locale("de"), id="to-de"),
            rx.button("en", on_click=rx.i18n.set_locale("en"), id="to-en"),
        )

    app = rx.App()
    app.add_page(index)

    # Set after App() because its __post_init__ reloads the config.
    rx.config.get_config().plugins = [
        rx.i18n.I18nPlugin(locales=["en", "de"], default_locale="en")
    ]


@pytest.fixture
def browser_context_args(browser_context_args: dict) -> dict:
    """Pin the browser locale and time zone for deterministic i18n output.

    The time zone is a negative offset (America/New_York) so a date-only value
    parsed as UTC midnight would visibly shift to the previous day, catching
    regressions in client-side date normalization.

    Args:
        browser_context_args: The default pytest-playwright context args.

    Returns:
        Context args with locale en-US and a fixed time zone.
    """
    return {
        **browser_context_args,
        "locale": "en-US",
        "timezone_id": "America/New_York",
    }


@pytest.fixture(scope="module")
def i18n_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Create a harness for the i18n app.

    Args:
        tmp_path_factory: Pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness for the test app.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("i18n_app"),
        app_source=I18nApp,
    ) as harness:
        yield harness


def test_static_translation_switches_locale(i18n_app: AppHarness, page: Page):
    """Static rx.t content switches locale instantly and persists via cookie.

    Args:
        i18n_app: Running harness for the i18n app.
        page: Playwright page.
    """
    assert i18n_app.frontend_url is not None
    page.goto(i18n_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    # Default locale (en): source text is shown.
    expect(page.locator("#static-hello")).to_have_text("Hello")
    expect(page.locator("#static-count")).to_have_text("1 item")

    # Switch to German: static content updates without a reload.
    page.click("#to-de")
    expect(page.locator("#static-hello")).to_have_text("Hallo")
    expect(page.locator("#static-count")).to_have_text("1 Artikel")

    # Plural boundary: 2 items still uses the (identical) German plural form.
    page.click("#inc")
    expect(page.locator("#static-count")).to_have_text("2 Artikel")

    # The chosen locale is persisted as a cookie.
    cookies = {c.get("name"): c.get("value") for c in page.context.cookies()}
    assert cookies.get("reflex_locale") == "de"

    # After reload the German locale is restored from the cookie.
    page.reload()
    expect(page.locator("#static-hello")).to_have_text("Hallo")

    # Switch back to English.
    page.click("#to-en")
    expect(page.locator("#static-hello")).to_have_text("Hello")
    expect(page.locator("#static-count")).to_have_text("2 items")


def test_dynamic_translation_uses_active_locale(i18n_app: AppHarness, page: Page):
    """Server-side gettext translates into the client's active locale.

    Args:
        i18n_app: Running harness for the i18n app.
        page: Playwright page.
    """
    assert i18n_app.frontend_url is not None
    page.goto(i18n_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    # In the default locale the handler emits the source text.
    page.click("#greet")
    expect(page.locator("#dynamic-message")).to_have_text("Welcome")

    # After switching to German, the same handler translates server-side.
    page.click("#to-de")
    page.click("#greet")
    expect(page.locator("#dynamic-message")).to_have_text("Willkommen")


def test_computed_var_retranslates_on_switch(i18n_app: AppHarness, page: Page):
    """A computed var calling gettext retranslates reactively on locale switch.

    This exercises auto-detected locale dependency injection: the getter never
    references the locale, yet switching locale recomputes and re-pushes it.

    Args:
        i18n_app: Running harness for the i18n app.
        page: Playwright page.
    """
    assert i18n_app.frontend_url is not None
    page.goto(i18n_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    # Rendered in the default locale on first load.
    expect(page.locator("#computed-greeting")).to_have_text("Welcome")

    # Switching locale alone (no other interaction) retranslates the computed
    # var via the auto-injected dependency on the active locale.
    page.click("#to-de")
    expect(page.locator("#computed-greeting")).to_have_text("Willkommen")

    page.click("#to-en")
    expect(page.locator("#computed-greeting")).to_have_text("Welcome")


def test_number_formatting_switches_locale(i18n_app: AppHarness, page: Page):
    """Client (Intl) and server (Babel) number formatting follow the locale.

    Args:
        i18n_app: Running harness for the i18n app.
        page: Playwright page.
    """
    assert i18n_app.frontend_url is not None
    page.goto(i18n_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    # Default locale (en): 1,234.50 for both client- and server-formatted.
    expect(page.locator("#client-number")).to_have_text("1,234.50")
    expect(page.locator("#server-number")).to_have_text("1,234.50")

    # German grouping/decimal separators, on both surfaces.
    page.click("#to-de")
    expect(page.locator("#client-number")).to_have_text("1.234,50")
    expect(page.locator("#server-number")).to_have_text("1.234,50")

    page.click("#to-en")
    expect(page.locator("#client-number")).to_have_text("1,234.50")


def test_client_date_and_time_formatting(i18n_app: AppHarness, page: Page):
    """Client-side date/time formatting parses Python values correctly.

    Under a negative-offset time zone, a date-only value must not shift to the
    previous day, and a time-only value must not render "Invalid Date".

    Args:
        i18n_app: Running harness for the i18n app.
        page: Playwright page.
    """
    assert i18n_app.frontend_url is not None
    page.goto(i18n_app.frontend_url)
    expect(page.locator("#token")).not_to_have_value("")

    # Date-only value: stays on the 18th (not the 17th) despite UTC-4.
    expect(page.locator("#client-date")).to_have_text("Jul 18, 2026")
    # Time-only value: formats as a time, never "Invalid Date".
    expect(page.locator("#client-time")).to_have_text("2:30 PM")

    # German locale reformats both without a day-shift.
    page.click("#to-de")
    expect(page.locator("#client-date")).to_have_text("18.07.2026")
    expect(page.locator("#client-time")).to_have_text("14:30")
