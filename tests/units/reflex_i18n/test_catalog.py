"""Tests for compiling .po catalogs into per-locale JS modules."""

import dataclasses

from babel.messages.catalog import Catalog
from reflex_i18n.catalog import compile_catalog_module, compile_index_module
from reflex_i18n.config import I18nConfig
from reflex_i18n.registry import MessageKey


def _catalog(locale: str = "de") -> Catalog:
    catalog = Catalog(locale=locale)
    catalog.add("Hello {name}!", "Hallo {name}!")
    catalog.add("Open", "Öffnen", context="menu")
    catalog.add(
        ("{count} item", "{count} items"),
        ("{count} Artikel", "{count} Artikel"),
    )
    return catalog


def test_compile_index_module():
    config = I18nConfig(locales=["en", "de"], default_locale="en")
    module = compile_index_module(config)
    assert 'export const locales = ["en", "de"];' in module
    assert 'export const defaultLocale = "en";' in module
    assert 'export const cookieName = "reflex_locale";' in module
    assert '"de": () => import("$/i18n/de.js"),' in module


def test_compile_catalog_includes_used_messages():
    used = [MessageKey("Hello {name}!"), MessageKey("Open", context="menu")]
    module = compile_catalog_module(_catalog(), used, "de", is_default_locale=False)
    assert '"Hello {name}!": "Hallo {name}!"' in module
    assert '"menu\\u0004Open": "\\u00d6ffnen"' in module
    assert "export const plural = (n) => Number((n != 1));" in module


def test_compile_catalog_tree_shakes_unused():
    # "Open" is in the catalog but not used; it must not be emitted.
    used = [MessageKey("Hello {name}!")]
    module = compile_catalog_module(_catalog(), used, "de", is_default_locale=False)
    assert "Open" not in module
    assert "Hallo" in module


def test_compile_catalog_plural_entry_is_array():
    used = [MessageKey("{count} item", "{count} items")]
    module = compile_catalog_module(_catalog(), used, "de", is_default_locale=False)
    assert '"{count} item": ["{count} Artikel", "{count} Artikel"]' in module


def test_compile_catalog_omits_untranslated():
    used = [MessageKey("Untranslated")]
    module = compile_catalog_module(_catalog(), used, "de", is_default_locale=False)
    assert "Untranslated" not in module
    assert "export const messages = {\n\n};" in module


def test_compile_catalog_no_catalog_falls_back():
    used = [MessageKey("Hello")]
    module = compile_catalog_module(None, used, "en", is_default_locale=True)
    assert "export const plural = (n) => Number(n != 1);" in module
    assert "Hello" not in module


def test_compile_catalog_polish_plural_expr():
    catalog = Catalog(locale="pl")
    module = compile_catalog_module(catalog, [], "pl", is_default_locale=False)
    # Polish has a 3-form plural; the C expression is whitelisted and kept.
    assert "n%10>=2" in module


@dataclasses.dataclass
class _FakeCatalog:
    """Minimal catalog stand-in for exercising plural-expr validation."""

    plural_expr: str


def test_compile_catalog_rejects_malicious_plural_expr():
    catalog = _FakeCatalog("alert('xss')")
    module = compile_catalog_module(catalog, [], "de", is_default_locale=False)  # pyright: ignore[reportArgumentType]
    assert "alert" not in module
    assert "export const plural = (n) => Number(n != 1);" in module
