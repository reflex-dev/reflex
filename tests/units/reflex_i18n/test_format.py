"""Tests for the client-side rx.i18n formatting vars."""

import pytest
from reflex_base.vars.base import Var
from reflex_i18n import I18nConfig, currency, date, datetime, number, percent, time
from reflex_i18n.component import I18nProvider
from reflex_i18n.config import set_active_i18n_config
from reflex_i18n.format import (
    _SOURCE_FMT_DATE,
    _SOURCE_FMT_LANGUAGE,
    _locale_var,
    language_name,
    locale_var,
    weekday,
)


@pytest.fixture(autouse=True)
def active_config():
    """Activate an i18n config for the formatting vars.

    Yields:
        None
    """
    # The locale var is a process-global cached singleton built under the
    # active config, so clear it on both sides to keep test order irrelevant.
    _locale_var.cache_clear()
    set_active_i18n_config(I18nConfig(locales=["en", "de"], default_locale="en"))
    yield
    set_active_i18n_config(None)
    _locale_var.cache_clear()


def _num() -> Var:
    return Var(_js_expr="state.value", _var_type=float)


def test_number_emits_fmt_number_call():
    var = number(_num())
    assert str(var) == "(fmtNumber(state.value, ({  })))"
    assert var._var_type is str


def test_number_curated_kwargs_map_to_intl_options():
    js = str(number(_num(), min_fraction_digits=1, max_fraction_digits=2))
    assert '["minimumFractionDigits"] : 1' in js
    assert '["maximumFractionDigits"] : 2' in js


def test_number_grouping_and_compact():
    js = str(number(_num(), grouping=False, compact=True))
    assert '["useGrouping"] : false' in js
    assert '["notation"] : "compact"' in js


def test_number_options_escape_hatch():
    js = str(number(_num(), options={"notation": "compact"}))
    assert '["notation"] : "compact"' in js


def test_currency_sets_style_and_currency():
    js = str(currency(_num(), "EUR"))
    assert '["style"] : "currency"' in js
    assert '["currency"] : "EUR"' in js


def test_percent_sets_style():
    js = str(percent(_num(), min_fraction_digits=1))
    assert '["style"] : "percent"' in js
    assert '["minimumFractionDigits"] : 1' in js


def test_date_uses_date_style():
    js = str(date(Var(_js_expr="state.day"), length="long"))
    assert js.startswith("(fmtDate(state.day")
    assert '["dateStyle"] : "long"' in js


def test_time_uses_time_style():
    js = str(time(Var(_js_expr="state.t"), length="short"))
    assert '["timeStyle"] : "short"' in js


def test_datetime_uses_both_styles():
    js = str(datetime(Var(_js_expr="state.dt")))
    assert '["dateStyle"] : "medium"' in js
    assert '["timeStyle"] : "medium"' in js


def test_format_var_data_injects_hook_and_provider():
    var_data = number(_num())._get_all_var_data()
    assert var_data is not None
    assert "const [ fmtNumber, fmtDate, fmtLanguage ] = useFormat()" in var_data.hooks
    assert any(lib == "$/utils/i18n" for lib, _ in var_data.imports)
    priority, provider = var_data.app_wraps[0]
    assert priority == 58
    assert isinstance(provider, I18nProvider)


def test_number_and_date_share_one_hook():
    combined = Var.create([number(_num()), date(Var(_js_expr="state.day"))])
    var_data = combined._get_all_var_data()
    assert var_data is not None
    hooks = [h for h in var_data.hooks if "useFormat" in h]
    assert hooks == ["const [ fmtNumber, fmtDate, fmtLanguage ] = useFormat()"]


def test_locale_var_reads_hook():
    var = _locale_var()
    assert str(var) == "i18nLocale"
    var_data = var._get_all_var_data()
    assert var_data is not None
    assert "const i18nLocale = useLocale()" in var_data.hooks


def test_shadowing_names_excluded_from_star_export():
    # date/time/datetime are reachable as attributes (rx.i18n.date) but kept
    # out of __all__ so `import *` cannot shadow the stdlib names.
    import reflex_i18n

    for name in ("date", "time", "datetime"):
        assert name not in reflex_i18n.__all__
        assert callable(getattr(reflex_i18n, name))
    # Non-shadowing formatters remain star-exported.
    for name in ("number", "currency", "percent"):
        assert name in reflex_i18n.__all__


def test_formatting_without_plugin_formats_inline_in_the_unconfigured_locale():
    # Without the plugin there is no client runtime to import from, so a
    # library's formatting var still builds and formats like the server does.
    set_active_i18n_config(None)
    var = number(_num())
    assert str(var) == (
        '(((value, options) => new Intl.NumberFormat("en", options).format(value))'
        "(state.value, ({  })))"
    )
    assert var._get_all_var_data() is None
    var = date(Var(_js_expr="state.day"))
    assert str(var) == (
        "(((value, options) => { "
        'const s = String(value).replace(/(\\.\\d{3})\\d+/, "$1"); '
        'return new Intl.DateTimeFormat("en", options).format('
        "value instanceof Date ? value "
        ': typeof value === "number" ? new Date(value) '
        ': /^\\d{4}-\\d{2}-\\d{2}$/.test(s) ? new Date(s + "T00:00:00") '
        ': /^\\d{2}:\\d{2}/.test(s) ? new Date("1970-01-01T" + s) '
        ': new Date(s.replace(" ", "T"))); })'
        '(state.day, ({ ["dateStyle"] : "medium" })))'
    )
    assert var._get_all_var_data() is None


def test_locale_var_without_plugin_is_the_unconfigured_locale():
    set_active_i18n_config(None)
    var = locale_var()
    assert str(var) == '"en"'
    assert var._get_all_var_data() is None


def test_format_vars_are_hashable():
    # Vars get hashed when their var data is merged, so the Intl options must
    # reach the formatter call as a Var rather than a raw dict.
    hash(number(_num()))
    hash(date(Var(_js_expr="state.day")))


@pytest.mark.parametrize("length", ["short", "full"])
def test_date_component_options_replace_the_curated_length(length: str):
    # Intl.DateTimeFormat throws when dateStyle/timeStyle are combined with
    # per-component options, so the escape hatch wins over `length`.
    js = str(
        date(Var(_js_expr="state.day"), length=length, options={"year": "numeric"})
    )
    assert "dateStyle" not in js
    assert '["year"] : "numeric"' in js
    js = str(time(Var(_js_expr="state.t"), options={"hour": "2-digit"}))
    assert "timeStyle" not in js


def test_date_non_component_options_keep_the_curated_length():
    js = str(date(Var(_js_expr="state.day"), options={"timeZone": "UTC"}))
    assert '["dateStyle"] : "medium"' in js
    assert '["timeZone"] : "UTC"' in js


def test_language_name_reads_the_format_hook():
    var = language_name(Var(_js_expr="state.tag", _var_type=str))
    assert str(var) == "(fmtLanguage(state.tag))"
    var_data = var._get_all_var_data()
    assert var_data is not None
    assert var_data.hooks == (
        "const [ fmtNumber, fmtDate, fmtLanguage ] = useFormat()",
    )


def test_weekday_formats_a_reference_date():
    var = weekday(Var(_js_expr="state.day", _var_type=int), length="short")
    assert str(var) == (
        '(fmtDate(new Date(2024, 0, 1 + state.day), ({ ["weekday"] : "short" })))'
    )


def test_language_name_and_weekday_without_plugin_format_inline():
    set_active_i18n_config(None)
    assert str(language_name("pt-BR")) == f'({_SOURCE_FMT_LANGUAGE!s}("pt-BR"))'
    assert str(weekday(2)) == (
        f'({_SOURCE_FMT_DATE!s}(new Date(2024, 0, 1 + 2), ({{ ["weekday"] : "long" }})))'
    )
