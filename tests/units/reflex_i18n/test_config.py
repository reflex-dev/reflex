"""Tests for the i18n configuration."""

import pytest
from reflex_i18n import I18nConfig
from reflex_i18n.config import get_active_i18n_config, set_active_i18n_config


def test_config_defaults():
    config = I18nConfig(locales=["en", "de"])
    assert config.locales == ("en", "de")
    assert config.default_locale == "en"
    assert config.catalog_dir == "locales"


def test_config_accepts_any_sequence():
    config = I18nConfig(locales=("de",), default_locale="de")
    assert config.locales == ("de",)


def test_config_requires_locales():
    with pytest.raises(ValueError, match="at least one locale"):
        I18nConfig(locales=[])


def test_config_default_locale_must_be_supported():
    with pytest.raises(ValueError, match="must be one of"):
        I18nConfig(locales=["en", "de"], default_locale="fr")


@pytest.mark.parametrize("locale", ["123", "e", "en/US", "en US", "", "de-"])
def test_config_rejects_invalid_locale(locale: str):
    with pytest.raises(ValueError, match="Invalid locale"):
        I18nConfig(locales=["en", locale])


def test_config_accepts_language_tags():
    config = I18nConfig(locales=["en", "pt-BR", "zh-Hant", "sr_Latn"])
    assert config.locales == ("en", "pt-BR", "zh-Hant", "sr_Latn")


def test_active_config_roundtrip():
    config = I18nConfig(locales=["en"])
    set_active_i18n_config(config)
    assert get_active_i18n_config() is config
    set_active_i18n_config(None)
    assert get_active_i18n_config() is None
