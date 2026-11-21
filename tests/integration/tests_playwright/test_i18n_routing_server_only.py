"""Integration tests for URL-based locale routing in an app without client translations.

App wraps are collected app-wide, so a single ``rx.t`` (or formatting var, or
language switcher) anywhere mounts the ``I18nProvider`` on every page. This app
uses none of them, which the app in ``test_i18n_routing.py`` cannot, and it gets
its own module for the same ``I18nState`` isolation reason as that one.
"""

import re
from collections.abc import Generator

import pytest
from playwright.sync_api import Page, expect

from reflex.testing import AppHarness


def I18nServerOnlyUrlApp():
    """URL-routing app translating only server-side, so no page mounts the provider."""
    from pathlib import Path

    import reflex as rx
    from reflex.i18n import gettext as _

    po_header = (
        'msgid ""\n'
        'msgstr ""\n'
        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
    )
    locales = Path("locales")
    locales.mkdir(exist_ok=True)
    (locales / "de.po").write_text(
        po_header + 'msgid "Welcome"\nmsgstr "Willkommen"\n', encoding="utf-8"
    )
    (locales / "en.po").write_text(po_header, encoding="utf-8")

    class UrlState(rx.State):
        @rx.var
        def greeting(self) -> str:
            return _("Welcome")

    def index():
        return rx.box(
            rx.input(
                value=UrlState.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.text(UrlState.greeting, id="dynamic"),
            rx.button("de", on_click=rx.i18n.set_locale("de"), id="to-de"),
            rx.button("en", on_click=rx.i18n.set_locale("en"), id="to-en"),
        )

    app = rx.App()
    app.add_page(index)

    rx.config.get_config().plugins = [
        rx.i18n.I18nPlugin(
            locales=["en", "de"],
            default_locale="en",
            routing=rx.i18n.PathPrefixRouting(),
        )
    ]


@pytest.fixture(scope="module")
def i18n_server_only_url_app(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppHarness, None, None]:
    """Create a harness for the server-only URL-routing app.

    Args:
        tmp_path_factory: Pytest fixture for creating temporary directories.

    Yields:
        Running AppHarness for the app.
    """
    with AppHarness.create(
        root=tmp_path_factory.mktemp("i18n_server_only_url_app"),
        app_source=I18nServerOnlyUrlApp,
    ) as harness:
        yield harness


def test_set_locale_navigates_without_provider(
    i18n_server_only_url_app: AppHarness, page: Page
):
    """``rx.i18n.set_locale`` navigates to the localized URL without a provider.

    Regression: on the default locale's unprefixed page nothing published the
    client setter, so the switch did nothing and the server event alone only
    wrote the cookie, which URL routing ignores.

    Args:
        i18n_server_only_url_app: Running harness for the app.
        page: Playwright page.
    """
    base = i18n_server_only_url_app.frontend_url
    assert base is not None
    base = base.rstrip("/")

    page.goto(base)
    expect(page.locator("#token")).not_to_have_value("")
    expect(page.locator("#dynamic")).to_have_text("Welcome")

    page.click("#to-de")
    expect(page).to_have_url(re.compile(re.escape(base) + r"/de/?$"))
    expect(page.locator("#dynamic")).to_have_text("Willkommen")
    expect(page.locator("html")).to_have_attribute("lang", "de")

    page.click("#to-en")
    expect(page).to_have_url(re.compile(re.escape(base) + r"/?$"))
    expect(page.locator("#dynamic")).to_have_text("Welcome")
