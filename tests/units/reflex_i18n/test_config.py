"""Tests for the i18n configuration."""

from pathlib import Path

import pytest
from reflex_i18n import I18nConfig
from reflex_i18n.config import (
    get_active_catalog_dirs,
    get_active_i18n_config,
    set_active_i18n_config,
)


def test_config_defaults():
    config = I18nConfig(locales=["en", "de"])
    assert config.locales == ("en", "de")
    assert config.default_locale == "en"
    assert config.catalog_dir == "locales"
    assert config.fallback_locale == "en"


def test_config_accepts_any_sequence():
    config = I18nConfig(locales=("de",), default_locale="de")
    assert config.locales == ("de",)


def test_config_requires_locales():
    with pytest.raises(ValueError, match="at least one locale"):
        I18nConfig(locales=[])


def test_config_default_locale_must_be_supported():
    with pytest.raises(ValueError, match="must be one of"):
        I18nConfig(locales=["en", "de"], default_locale="fr")


def test_config_fallback_locale_defaults_to_default_locale():
    config = I18nConfig(locales=["de", "en"], default_locale="de")
    assert config.fallback_locale == "de"


def test_config_fallback_locale_must_be_supported():
    with pytest.raises(ValueError) as exc_info:
        I18nConfig(locales=["de", "en"], default_locale="de", fallback_locale="fr")
    assert str(exc_info.value) == (
        "I18nConfig.fallback_locale 'fr' must be one of the configured locales "
        "('de', 'en')."
    )


@pytest.mark.parametrize(
    "locale", ["123", "e", "en/US", "en US", "", "de-", "en\n", "sr_Latn", "en_US"]
)
def test_config_rejects_invalid_locale(locale: str):
    # Underscore tags are rejected rather than normalized: a locale is used
    # verbatim as a URL segment, an Intl tag and an Accept-Language match.
    with pytest.raises(ValueError, match="Invalid locale"):
        I18nConfig(locales=["en", locale])


def test_config_accepts_language_tags():
    config = I18nConfig(locales=["en", "pt-BR", "zh-Hant"])
    assert config.locales == ("en", "pt-BR", "zh-Hant")


def test_config_rejects_duplicate_locales():
    with pytest.raises(ValueError, match="must not repeat"):
        I18nConfig(locales=["en", "de", "en"])


def test_active_config_roundtrip():
    config = I18nConfig(locales=["en"])
    set_active_i18n_config(config)
    assert get_active_i18n_config() is config
    set_active_i18n_config(None)
    assert get_active_i18n_config() is None


def test_activating_resolves_catalog_package_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    package_dir = tmp_path / "site" / "mylib"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path / "site"))

    config = I18nConfig(locales=["en"], catalog_packages=["mylib"])
    assert config.catalog_packages == ("mylib",)
    set_active_i18n_config(config)
    try:
        assert get_active_catalog_dirs() == (
            (tmp_path / "locales").resolve(),
            package_dir.resolve() / "locales",
        )
    finally:
        set_active_i18n_config(None)
    assert get_active_catalog_dirs() == ()


def test_activating_an_uninstalled_catalog_package_fails():
    config = I18nConfig(locales=["en"], catalog_packages=["no_such_i18n_package"])
    with pytest.raises(ValueError) as exc_info:
        set_active_i18n_config(config)
    assert str(exc_info.value) == (
        "Cannot find the package 'no_such_i18n_package': it is not installed."
    )
    assert get_active_i18n_config() is None
