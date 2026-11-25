"""Tests for the URL helpers of locale routing."""

import pytest
from reflex_base.config import get_config
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import VarData
from reflex_i18n import (
    I18nPlugin,
    PathPrefixRouting,
    alternate_url,
    locale_url,
    localized_url,
    path_redirects,
)
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


@pytest.mark.usefixtures("url_routing")
def test_alternate_url_reads_the_current_page_in_a_locale():
    var = alternate_url("en")
    assert str(var) == 'i18nAlternateUrls?.["en"]'
    assert var._get_all_var_data() == VarData(
        imports={"$/utils/i18n": [ImportVar(tag="useAlternateUrls")]},
        hooks={"const i18nAlternateUrls = useAlternateUrls()": None},
    )


@pytest.mark.usefixtures("url_routing")
def test_alternate_url_rejects_an_unconfigured_locale():
    with pytest.raises(ValueError, match=r"^Locale 'fr' is not configured\. "):
        alternate_url("fr")


def test_alternate_url_is_the_page_itself_without_i18n():
    assert str(alternate_url("de")) == '""'


@pytest.fixture
def translated_news(monkeypatch: pytest.MonkeyPatch):
    """Configure URL routing with a news page whose English path is translated.

    Args:
        monkeypatch: Sets the config's plugins and frontend path for the test.
    """
    plugin = I18nPlugin(
        locales=["de", "en"], default_locale="de", routing=PathPrefixRouting()
    )
    plugin._page_paths = {"/neuigkeiten": {"en": "/news"}}
    monkeypatch.setattr(get_config(), "plugins", [plugin])


@pytest.mark.usefixtures("translated_news")
def test_links_lead_to_a_pages_translated_path():
    assert locale_url("en", "/neuigkeiten") == "/en/news"
    assert locale_url("de", "/neuigkeiten") == "/neuigkeiten"
    with use_locale("en"):
        assert localized_url("neuigkeiten") == "/en/news"


@pytest.mark.usefixtures("translated_news")
@pytest.mark.parametrize(("frontend_path", "prefix"), [("", ""), ("/app/", "/app")])
def test_path_redirects_name_server_paths(
    monkeypatch: pytest.MonkeyPatch, frontend_path: str, prefix: str
):
    monkeypatch.setattr(get_config(), "frontend_path", frontend_path)
    assert path_redirects() == {
        f"{prefix}/news": f"{prefix}/neuigkeiten",
        f"{prefix}/en/neuigkeiten": f"{prefix}/en/news",
    }


def test_path_redirects_are_empty_without_routing(monkeypatch: pytest.MonkeyPatch):
    plugin = I18nPlugin(locales=["de", "en"], default_locale="de")
    monkeypatch.setattr(get_config(), "plugins", [plugin])
    assert path_redirects() == {}
