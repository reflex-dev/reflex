"""Tests for the I18nPlugin: config activation and catalog emission."""

from pathlib import Path

import pytest
from reflex_i18n import I18nPlugin, t
from reflex_i18n.config import set_active_i18n_config
from reflex_i18n.registry import clear_messages


@pytest.fixture(autouse=True)
def clean_registry():
    """Isolate the message registry and global config per test.

    Yields:
        None
    """
    clear_messages()
    set_active_i18n_config(None)
    yield
    clear_messages()
    set_active_i18n_config(None)


def _write_po(catalog_dir: Path, locale: str, body: str) -> None:
    catalog_dir.mkdir(parents=True, exist_ok=True)
    header = (
        'msgid ""\nmsgstr ""\n'
        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'
    )
    (catalog_dir / f"{locale}.po").write_text(header + body, encoding="utf-8")


def test_plugin_activates_config():
    I18nPlugin(locales=["en", "de"], default_locale="en")
    # rx.t requires an active config; constructing the plugin provides it.
    var = t("Hello")
    assert 't_("Hello"' in str(var)


def test_t_without_plugin_raises():
    with pytest.raises(RuntimeError, match="requires the i18n plugin"):
        t("Hello")


def test_plugin_ships_client_runtime():
    plugin = I18nPlugin(locales=["en"])
    assets = dict(plugin.get_static_assets())
    runtime = assets[Path("utils/i18n.js")]
    assert isinstance(runtime, str)
    assert "useTranslation" in runtime


def test_plugin_emits_index_and_locale_modules(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_po(tmp_path / "locales", "de", 'msgid "Hello"\nmsgstr "Hallo"\n')

    plugin = I18nPlugin(locales=["en", "de"], default_locale="en")
    t("Hello")

    outputs = dict(plugin._compile_catalogs())
    assert set(outputs) == {"i18n/index.js", "i18n/en.js", "i18n/de.js"}
    assert '"de": () => import("$/i18n/de.js")' in outputs["i18n/index.js"]
    assert '"Hello": "Hallo"' in outputs["i18n/de.js"]
    # The default (source) locale needs no translation entry.
    assert '"Hello"' not in outputs["i18n/en.js"]


def test_plugin_missing_catalog_file_still_emits_module(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    plugin = I18nPlugin(locales=["en", "de"], default_locale="en")
    t("Hello")

    outputs = dict(plugin._compile_catalogs())
    # de.js exists but is empty (falls back to source text at runtime).
    assert "i18n/de.js" in outputs
    assert "export const messages" in outputs["i18n/de.js"]
