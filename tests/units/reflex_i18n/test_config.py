"""Tests for the i18n configuration."""

from pathlib import Path

import pytest
from reflex_i18n import I18nConfig
from reflex_i18n.config import (
    get_active_catalog_dirs,
    get_active_i18n_config,
    normalize_locale,
    set_active_i18n_config,
    source_locale,
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


@pytest.mark.parametrize("locales", [("en", "de", "en"), ("en", "de", "EN")])
def test_config_rejects_duplicate_locales(locales: tuple[str, ...]):
    # Case-only repeats too: the router and catalog lookups ignore case, so
    # client and server would each pick a different one of the two.
    with pytest.raises(ValueError) as exc_info:
        I18nConfig(locales=locales)
    assert str(exc_info.value) == (
        "I18nConfig.locales must not repeat a locale (tags are case-insensitive): "
        f"{locales!r}."
    )


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


@pytest.mark.parametrize("package", ["no_such_i18n_package", "no_such_i18n_package.ui"])
def test_activating_an_uninstalled_catalog_package_fails(package: str):
    active = I18nConfig(locales=["en"])
    set_active_i18n_config(active)
    try:
        with pytest.raises(ValueError) as exc_info:
            set_active_i18n_config(
                I18nConfig(locales=["en"], catalog_packages=[package])
            )
        assert str(exc_info.value) == (
            f"Cannot find the package {package!r}: it is not installed."
        )
        # The failed activation leaves the previous config in place.
        assert get_active_i18n_config() is active
    finally:
        set_active_i18n_config(None)


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        ("DE", "de"),
        ("pt-br", "pt-BR"),
        ("ZH-hant-tw", "zh-Hant-TW"),
        ("es-419", "es-419"),
        ("sl-ROZAJ", "sl-rozaj"),
        ("sl-latn-it-NEDIS", "sl-Latn-IT-nedis"),
        ("EN-us-U-CA-Gregory", "en-US-u-ca-gregory"),
        ("de-X-ABCD-DE", "de-x-abcd-de"),
    ],
)
def test_normalize_locale_uses_the_conventional_case(locale: str, expected: str):
    assert normalize_locale(locale) == expected


def test_normalize_locale_prefers_the_configured_spelling():
    set_active_i18n_config(I18nConfig(locales=["en", "PT-br"]))
    try:
        assert normalize_locale("pt-BR") == "PT-br"
        assert normalize_locale("en-us") == "en-US"
    finally:
        set_active_i18n_config(None)


def test_normalize_locale_rejects_invalid_tags():
    with pytest.raises(ValueError) as exc_info:
        normalize_locale("en_US")
    assert str(exc_info.value) == (
        "Invalid locale 'en_US': expected a hyphen-separated language tag such as "
        "'en', 'pt-BR' or 'zh-Hant'."
    )


def test_source_locale_is_the_default_locale():
    assert source_locale() == "en"
    set_active_i18n_config(I18nConfig(locales=["de", "en"], default_locale="de"))
    try:
        assert source_locale() == "de"
    finally:
        set_active_i18n_config(None)
