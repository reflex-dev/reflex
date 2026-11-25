"""Tests for the URL helpers of locale routing."""

import pytest
from reflex_base.config import get_config
from reflex_i18n import I18nPlugin, PathPrefixRouting, locale_url, localized_url
from reflex_i18n.config import set_active_i18n_config
from reflex_i18n.runtime import use_locale


@pytest.fixture(autouse=True)
def clean_config():
    """Deactivate the config a test's plugin activated.

    Yields:
        None
    """
    yield
    set_active_i18n_config(None)


@pytest.fixture
def url_routing(monkeypatch: pytest.MonkeyPatch):
    """Configure German and English with URL routing, German at the root.

    Args:
        monkeypatch: Sets the config's plugins for the test.
    """
    plugin = I18nPlugin(
        locales=["de", "en"], default_locale="de", routing=PathPrefixRouting()
    )
    monkeypatch.setattr(get_config(), "plugins", [plugin])


@pytest.mark.usefixtures("url_routing")
@pytest.mark.parametrize(
    ("locale", "route", "expected"),
    [
        ("de", "index", "/"),
        ("de", "/help/terminal", "/help/terminal"),
        ("en", "/", "/en"),
        ("en", "help/terminal", "/en/help/terminal"),
    ],
)
def test_locale_url_localizes_a_route(locale: str, route: str, expected: str):
    assert locale_url(locale, route) == expected


@pytest.mark.usefixtures("url_routing")
@pytest.mark.parametrize(
    ("locale", "expected"),
    [("de", "/help/terminal"), ("en", "/en/help/terminal"), (None, "/help/terminal")],
)
def test_localized_url_follows_the_locale_a_page_is_built_in(
    locale: str | None, expected: str
):
    """Outside any locale it falls back to the default locale, as gettext does."""
    with use_locale(locale):
        assert localized_url("/help/terminal") == expected


def test_localized_url_leaves_the_route_alone_without_routing(
    monkeypatch: pytest.MonkeyPatch,
):
    plugin = I18nPlugin(locales=["de", "en"], default_locale="de")
    monkeypatch.setattr(get_config(), "plugins", [plugin])
    with use_locale("en"):
        assert localized_url("/help/terminal") == "/help/terminal"
