"""Tests for server-side gettext translation of dynamic content."""

from pathlib import Path

import pytest
from reflex_i18n.config import I18nConfig, set_active_i18n_config
from reflex_i18n.runtime import (
    clear_translations_cache,
    gettext,
    negotiate_locale,
    ngettext,
    pgettext,
    use_locale,
)


@pytest.fixture(autouse=True)
def clean_state():
    """Reset the translation cache and active config per test.

    Yields:
        None
    """
    clear_translations_cache()
    set_active_i18n_config(None)
    yield
    clear_translations_cache()
    set_active_i18n_config(None)


def _write_po(catalog_dir: Path, locale: str, body: str) -> None:
    catalog_dir.mkdir(parents=True, exist_ok=True)
    header = (
        'msgid ""\nmsgstr ""\n'
        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
    )
    (catalog_dir / f"{locale}.po").write_text(header + body, encoding="utf-8")


def test_gettext_without_locale_returns_source():
    assert gettext("Hello") == "Hello"


def test_gettext_translates_active_locale(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_po(tmp_path / "locales", "de", 'msgid "Hello"\nmsgstr "Hallo"\n')
    set_active_i18n_config(I18nConfig(locales=["en", "de"], default_locale="en"))

    with use_locale("de"):
        assert gettext("Hello") == "Hallo"
    assert gettext("Hello") == "Hello"


def test_gettext_missing_translation_falls_back(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_po(tmp_path / "locales", "de", 'msgid "Hello"\nmsgstr "Hallo"\n')
    set_active_i18n_config(I18nConfig(locales=["en", "de"], default_locale="en"))

    with use_locale("de"):
        assert gettext("Goodbye") == "Goodbye"


def test_ngettext_plural(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_po(
        tmp_path / "locales",
        "de",
        'msgid "{n} item"\nmsgid_plural "{n} items"\n'
        'msgstr[0] "{n} Artikel"\nmsgstr[1] "{n} Artikel"\n',
    )
    set_active_i18n_config(I18nConfig(locales=["en", "de"], default_locale="en"))

    with use_locale("de"):
        assert ngettext("{n} item", "{n} items", 1) == "{n} Artikel"
        assert ngettext("{n} item", "{n} items", 3) == "{n} Artikel"


def test_ngettext_without_locale():
    assert ngettext("one", "many", 1) == "one"
    assert ngettext("one", "many", 2) == "many"


def test_pgettext_context(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_po(
        tmp_path / "locales",
        "de",
        'msgctxt "menu"\nmsgid "Open"\nmsgstr "Öffnen"\n',
    )
    set_active_i18n_config(I18nConfig(locales=["en", "de"], default_locale="en"))

    with use_locale("de"):
        assert pgettext("menu", "Open") == "Öffnen"


def test_negotiate_locale_exact_match():
    assert negotiate_locale("de-DE,de;q=0.9", ["en", "de"], "en") == "de"


def test_negotiate_locale_language_prefix():
    assert negotiate_locale("de-AT", ["en", "de"], "en") == "de"


def test_negotiate_locale_quality_order():
    assert negotiate_locale("fr;q=0.2,de;q=0.8", ["en", "de", "fr"], "en") == "de"


def test_negotiate_locale_falls_back_to_default():
    assert negotiate_locale("ja,ko", ["en", "de"], "en") == "en"


def test_negotiate_locale_ignores_wildcard():
    assert negotiate_locale("*", ["en", "de"], "en") == "en"


def test_negotiate_locale_excludes_q0():
    # q=0 means "not acceptable" (RFC 7231): de must not be matched even though
    # it is supported, and negotiation falls back to the default.
    assert negotiate_locale("de;q=0", ["en", "de"], "en") == "en"
    # A q=0 locale is excluded even when it is the only supported candidate.
    assert negotiate_locale("de;q=0,fr;q=0.9", ["en", "de"], "en") == "en"
