"""Tests for URL-based locale routing (fan-out, hreflang, strategies)."""

import types

import pytest
from reflex_i18n import I18nConfig, PathPrefixRouting
from reflex_i18n.catalog import compile_index_module
from reflex_i18n.config import set_active_i18n_config
from reflex_i18n.plugin import I18nPlugin, _catalog_ident, _catalog_var

LOCALES = ["en", "de", "fr"]


@pytest.fixture(autouse=True)
def active_config():
    """Activate an i18n config for the routing helpers.

    Yields:
        None
    """
    set_active_i18n_config(I18nConfig(locales=LOCALES, default_locale="en"))
    yield
    set_active_i18n_config(None)


def test_path_prefix_localize_default_at_root():
    r = PathPrefixRouting()
    assert r.localize("/", "en", "en") == "/"
    assert r.localize("/", "de", "en") == "/de"
    assert r.localize("/pricing", "en", "en") == "/pricing"
    assert r.localize("/pricing", "de", "en") == "/de/pricing"


def test_path_prefix_localize_prefix_all():
    r = PathPrefixRouting(default_at_root=False)
    assert r.localize("/pricing", "en", "en") == "/en/pricing"
    assert r.localize("/pricing", "de", "en") == "/de/pricing"


def test_path_prefix_delocalize_and_locale_of():
    r = PathPrefixRouting()
    assert r.delocalize("/de/pricing", LOCALES) == "/pricing"
    assert r.delocalize("/pricing", LOCALES) == "/pricing"
    assert r.delocalize("/de", LOCALES) == "/"
    assert r.locale_of("/de/pricing", LOCALES, "en") == "de"
    assert r.locale_of("/pricing", LOCALES, "en") == "en"


def test_path_prefix_alternates():
    r = PathPrefixRouting()
    assert r.alternates("/de/pricing", LOCALES, "en") == {
        "en": "/pricing",
        "de": "/de/pricing",
        "fr": "/fr/pricing",
    }


def test_index_module_exports_routing_config():
    js = compile_index_module(
        I18nConfig(locales=LOCALES, default_locale="en"),
        url_routing=True,
        default_at_root=True,
        deploy_url="https://site.com",
    )
    assert "export const urlRouting = true;" in js
    assert "export const defaultAtRoot = true;" in js
    assert 'export const deployUrl = "https://site.com";' in js


def test_catalog_var_static_namespace_import():
    var = _catalog_var("en-US")
    assert _catalog_ident("en-US") == "en_USCatalog"
    assert str(var) == "en_USCatalog"
    var_data = var._get_all_var_data()
    assert var_data is not None
    imports = dict(var_data.imports)
    entry = imports["$/i18n/en-US.js"]
    assert (entry[0].tag, entry[0].alias, entry[0].is_default) == (
        "*",
        "en_USCatalog",
        True,
    )


def _page(route, component=None):
    return types.SimpleNamespace(
        route=route,
        component=component or (lambda: None),
        title=None,
        description=None,
        image="",
        on_load=None,
        meta=(),
        context=None,
    )


def _fake_context(pages):
    calls = []

    def add_page(component=None, route=None, **kwargs):
        calls.append((route, kwargs))

    return {"add_page": add_page, "pages": pages, "calls": calls}


def test_expand_routes_fans_out_non_default_locales():
    plugin = I18nPlugin(
        locales=LOCALES, default_locale="en", routing=PathPrefixRouting()
    )
    ctx = _fake_context([_page("index"), _page("pricing")])
    plugin.expand_routes(add_page=ctx["add_page"], pages=ctx["pages"])  # pyright: ignore[reportCallIssue]

    routes = sorted(route for route, _ in ctx["calls"])
    # Default locale (en) is served by the app's own routes -> not fanned.
    assert routes == ["/de", "/de/pricing", "/fr", "/fr/pricing"]
    # Each fanned page records its locale in the page context.
    locales = {route: kw["context"]["i18n_locale"] for route, kw in ctx["calls"]}
    assert locales["/de/pricing"] == "de"
    assert locales["/fr"] == "fr"


def test_expand_routes_noop_without_routing():
    plugin = I18nPlugin(locales=LOCALES, default_locale="en")
    ctx = _fake_context([_page("index")])
    plugin.expand_routes(add_page=ctx["add_page"], pages=ctx["pages"])  # pyright: ignore[reportCallIssue]
    assert ctx["calls"] == []


def test_compile_page_injects_hreflang_when_routing():
    plugin = I18nPlugin(
        locales=LOCALES, default_locale="en", routing=PathPrefixRouting()
    )
    page_ctx = types.SimpleNamespace(route="index", app_wrap_components={})
    plugin.compile_page(page_ctx)  # pyright: ignore[reportArgumentType]
    keys = list(page_ctx.app_wrap_components)
    assert any(name == "HreflangLinks" for _, name in keys)


def test_compile_page_noop_without_routing():
    plugin = I18nPlugin(locales=LOCALES, default_locale="en")
    page_ctx = types.SimpleNamespace(route="index", app_wrap_components={})
    plugin.compile_page(page_ctx)  # pyright: ignore[reportArgumentType]
    assert page_ctx.app_wrap_components == {}


def test_plugin_rejects_custom_routing():
    from reflex_i18n.routing import LocaleRouting

    class DomainRouting(LocaleRouting):
        def localize(self, path, locale, default_locale):
            return path

        def delocalize(self, path, locales):
            return path

        def locale_of(self, path, locales, default_locale):
            return default_locale

    with pytest.raises(TypeError, match="PathPrefixRouting"):
        I18nPlugin(locales=LOCALES, routing=DomainRouting())  # pyright: ignore[reportArgumentType]


def test_expand_routes_rejects_locale_prefixed_app_route():
    from reflex_base.utils.exceptions import RouteValueError

    plugin = I18nPlugin(
        locales=LOCALES, default_locale="en", routing=PathPrefixRouting()
    )
    ctx = _fake_context([_page("de/pricing")])
    with pytest.raises(RouteValueError, match="reserved"):
        plugin.expand_routes(add_page=ctx["add_page"], pages=ctx["pages"])  # pyright: ignore[reportCallIssue]


def test_expand_routes_rejects_bare_locale_app_route():
    from reflex_base.utils.exceptions import RouteValueError

    plugin = I18nPlugin(
        locales=LOCALES, default_locale="en", routing=PathPrefixRouting()
    )
    ctx = _fake_context([_page("fr")])
    with pytest.raises(RouteValueError, match="reserved"):
        plugin.expand_routes(add_page=ctx["add_page"], pages=ctx["pages"])  # pyright: ignore[reportCallIssue]
