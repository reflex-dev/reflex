"""Tests for server-side gettext translation of dynamic content."""

import datetime
from pathlib import Path

import pytest
from reflex_i18n.config import I18nConfig, set_active_i18n_config
from reflex_i18n.runtime import (
    clear_translations_cache,
    format_currency,
    format_date,
    format_datetime,
    format_decimal,
    format_number,
    format_percent,
    format_time,
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


def test_format_number_localized():
    with use_locale("de"):
        assert format_number(1234567.891, max_fraction_digits=2) == "1.234.567,89"
    with use_locale("en"):
        assert format_number(1234567.891, max_fraction_digits=2) == "1,234,567.89"


def test_format_number_grouping_and_fraction_bounds():
    with use_locale("en"):
        assert format_number(1234.5, grouping=False) == "1234.5"
        assert format_number(1, min_fraction_digits=2) == "1.00"


def test_format_number_compact():
    with use_locale("en"):
        assert format_number(1200000, compact=True) == "1M"
        assert format_number(1200000, compact=True, max_fraction_digits=1) == "1.2M"


def test_format_decimal_is_format_number():
    assert format_decimal is format_number


def test_format_currency_localized():
    with use_locale("de"):
        assert format_currency(1234.5, "EUR") == "1.234,50\xa0€"
    with use_locale("en"):
        assert format_currency(1234.5, "EUR") == "€1,234.50"


def test_format_percent_localized():
    # Locale default digits; de keeps its non-breaking space before "%".
    with use_locale("de"):
        assert format_percent(0.5) == "50\xa0%"
    with use_locale("en"):
        assert format_percent(0.5) == "50%"


def test_format_percent_fraction_digits_preserve_affix():
    # Fraction digits apply without losing the locale's "%" spacing.
    with use_locale("de"):
        assert format_percent(0.1234, max_fraction_digits=1) == "12,3\xa0%"
    with use_locale("en"):
        assert format_percent(0.1234, max_fraction_digits=1) == "12.3%"


def test_format_currency_fraction_digits():
    with use_locale("de"):
        assert format_currency(1234.5, "EUR", max_fraction_digits=1) == "1.234,5\xa0€"
        assert format_currency(1234.5, "EUR", min_fraction_digits=3) == "1.234,500\xa0€"
    with use_locale("en"):
        assert format_currency(1234.5, "USD", min_fraction_digits=3) == "$1,234.500"


def test_format_number_preserves_native_grouping():
    # Indian grouping (lakh/crore) is preserved, not forced to Western groups.
    with use_locale("en-IN"):
        assert format_number(1234567) == "12,34,567"


def test_format_hyphenated_locale():
    # Babel needs 'en_US'; the helper normalizes '-' so BCP-47 tags work.
    with use_locale("en-US"):
        assert format_number(1234.5, max_fraction_digits=1) == "1,234.5"


def test_format_date_localized():
    day = datetime.date(2026, 3, 18)
    with use_locale("de"):
        assert format_date(day, length="long") == "18. März 2026"
    with use_locale("en"):
        assert format_date(day, length="long") == "March 18, 2026"


def test_format_time_localized():
    moment = datetime.datetime(2026, 7, 18, 14, 30)
    with use_locale("de"):
        assert format_time(moment, length="short") == "14:30"


def test_format_datetime_localized():
    moment = datetime.datetime(2026, 7, 18, 14, 30)
    with use_locale("de"):
        assert format_datetime(moment, length="short") == "18.07.26, 14:30"


def test_format_falls_back_to_default_locale_without_active():
    set_active_i18n_config(I18nConfig(locales=["de", "en"], default_locale="de"))
    # No active locale in context -> uses the configured default (de).
    assert format_number(1234.5, max_fraction_digits=1) == "1.234,5"


def test_format_falls_back_to_en_without_config():
    # No active locale and no config -> plain en-US formatting.
    assert format_number(1234.5, max_fraction_digits=1) == "1,234.5"


def test_format_functions_registered_as_locale_dependencies():
    # Importing the runtime registers the format helpers so a computed var
    # using one reformats when the locale changes (like gettext).
    from reflex_base.vars.dep_tracking import _implicit_dependency_providers

    for fn in (
        format_number,
        format_currency,
        format_percent,
        format_date,
        format_time,
        format_datetime,
    ):
        assert fn in _implicit_dependency_providers


async def test_format_computed_var_reformats_on_locale_change():
    """A format_* computed var recomputes and re-emits in the new locale.

    Exercises the full automatic path without a browser: the real module-level
    registration wires the locale dependency, and changing the locale cookie
    dirties the computed var so it is recomputed (in the new locale) and lands
    in the delta.
    """
    from reflex_i18n.state import I18nState

    import reflex as rx
    from reflex.state import State as RootState

    set_active_i18n_config(I18nConfig(locales=["en", "de"], default_locale="en"))
    # Defining a state that depends on I18nState.locale registers a permanent
    # cross-state edge on the shared I18nState class; snapshot and restore it.
    saved_deps = {k: set(v) for k, v in I18nState._var_dependencies.items()}
    saved_dirty = set(I18nState._potentially_dirty_states)
    try:

        class LocalePriceState(rx.State):
            amount: float = 1234.5

            @rx.var
            def price(self) -> str:
                return format_number(self.amount, max_fraction_digits=1)

        # The real (non-mocked) registration wired the locale dependency.
        deps = LocalePriceState.computed_vars["price"]._deps(objclass=LocalePriceState)
        assert deps.get(I18nState.get_full_name()) == {"locale"}

        root = RootState(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]
        i18n = await root.get_state(I18nState)
        price_state = await root.get_state(LocalePriceState)

        # Cached in the default locale (en), then dirties are cleared.
        assert price_state.price == "1,234.5"
        root._clean()

        # Switching the locale dirties the computed var; it recomputes in the
        # active locale and is re-emitted in the delta.
        i18n.locale_cookie = "de"
        with use_locale("de"):
            delta = await root._get_resolved_delta()

        values = [v for substate in delta.values() for v in substate.values()]
        assert "1.234,5" in values
        assert "1,234.5" not in values
    finally:
        I18nState._var_dependencies = saved_deps
        I18nState._potentially_dirty_states = saved_dirty
        set_active_i18n_config(None)
