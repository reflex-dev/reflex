"""Integration tests for URL-based locale routing + hreflang (SEO).

Kept in its own module so its i18n app does not coexist with the cookie-mode
app in ``test_i18n.py``: ``I18nState`` is a process-global substate, and two
i18n ``AppHarness`` apps alive at once accumulate cross-state edges on it.
Module-scoped fixtures tear down (and ``reload_state_module``) at module end,
so a separate module gets a clean ``I18nState``.
"""

from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def I18nUrlApp():
    """App exercising URL-based locale routing + hreflang (SEO)."""
    from pathlib import Path

    import reflex as rx
    from reflex.i18n import gettext as _

    po_header = (
        'msgid ""\n'
        'msgstr ""\n'
        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
    )
    de_po = po_header + (
        'msgid "Hello"\nmsgstr "Hallo"\n\nmsgid "Welcome"\nmsgstr "Willkommen"\n'
    )
    locales = Path("locales")
    locales.mkdir(exist_ok=True)
    (locales / "de.po").write_text(de_po, encoding="utf-8")
    (locales / "en.po").write_text(po_header, encoding="utf-8")

    class UrlState(rx.State):
        @rx.var
        def greeting(self) -> str:
            # Dynamic (server) gettext; must follow the URL locale.
            return _("Welcome")

    def index():
        return rx.box(
            rx.input(
                value=UrlState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.text(rx.t("Hello"), id="static"),
            rx.text(UrlState.greeting, id="dynamic"),
            rx.text(rx.i18n.locale, id="locale"),
            rx.i18n.language_switcher(id="switcher"),
        )

    app = rx.App()
    app.add_page(index)

    cfg = rx.config.get_config()
    cfg.deploy_url = "https://example.com"
    cfg.plugins = [
        rx.i18n.I18nPlugin(
            locales=["en", "de"],
            default_locale="en",
            routing=rx.i18n.PathPrefixRouting(),
        )
    ]


@pytest.fixture
def browser_context_args(browser_context_args: dict) -> dict:
    """Pin the browser locale so locale negotiation is deterministic.

    Args:
        browser_context_args: The default pytest-playwright context args.

    Returns:
        Context args with the locale forced to en-US.
    """
    return {**browser_context_args, "locale": "en-US"}


@pytest.fixture(scope="module")
def i18n_url_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Create a harness for the URL-routing i18n app.

    Args:
        tmp_path_factory: Pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness for the URL-routing app.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("i18n_url_app"),
        app_source=I18nUrlApp,
    ) as harness:
        yield harness


def test_url_locale_routing(i18n_url_app: AppHarness, page: Page):
    """A per-locale URL renders that language and emits reciprocal hreflang.

    Args:
        i18n_url_app: Running harness for the URL-routing app.
        page: Playwright page.
    """
    base = i18n_url_app.frontend_url
    assert base is not None

    # Default route: English.
    page.goto(base)
    expect(page.locator("#static")).to_have_text("Hello")
    expect(page.locator("#dynamic")).to_have_text("Welcome")

    # /de renders German for both static (rx.t) and dynamic (gettext) content,
    # sets <html lang="de">, and exposes the active locale from the URL.
    page.goto(base.rstrip("/") + "/de")
    expect(page.locator("#static")).to_have_text("Hallo")
    expect(page.locator("#dynamic")).to_have_text("Willkommen")
    expect(page.locator("#locale")).to_have_text("de")
    expect(page.locator("html")).to_have_attribute("lang", "de")

    # Reciprocal hreflang alternates are present in the head.
    alternates = page.eval_on_selector_all(
        "link[rel=alternate]",
        "els => els.map(e => e.getAttribute('hreflang'))",
    )
    assert {"en", "de", "x-default"} <= set(alternates)


def test_url_locale_wins_over_cookie(i18n_url_app: AppHarness, page: Page):
    """With URL routing, the URL names the locale; a stored cookie never does.

    Regression: the provider used to apply the cookie/browser locale on the
    default-at-root page, so `/` rendered German for a visitor with a stored
    `de` preference even though the URL says default locale.

    Args:
        i18n_url_app: Running harness for the URL-routing app.
        page: Playwright page.
    """
    base = i18n_url_app.frontend_url
    assert base is not None

    page.context.add_cookies([{"name": "reflex_locale", "value": "de", "url": base}])
    page.goto(base)
    expect(page.locator("#static")).to_have_text("Hello")
    expect(page.locator("#locale")).to_have_text("en")
    expect(page.locator("html")).to_have_attribute("lang", "en")

    # The canonical link points at the page's own URL.
    canonical = page.locator("link[rel=canonical]")
    expect(canonical).to_have_attribute("href", "https://example.com/")
