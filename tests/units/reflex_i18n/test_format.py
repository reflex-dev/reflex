"""Tests for the client-side rx.i18n formatting vars."""

import pytest
from reflex_base.vars.base import Var
from reflex_i18n import I18nConfig, currency, date, datetime, number, percent, time
from reflex_i18n.component import I18nProvider
from reflex_i18n.config import set_active_i18n_config
from reflex_i18n.format import _locale_var


@pytest.fixture(autouse=True)
def active_config():
    """Activate an i18n config for the formatting vars.

    Yields:
        None
    """
    set_active_i18n_config(I18nConfig(locales=["en", "de"], default_locale="en"))
    yield
    set_active_i18n_config(None)


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
    assert "const [ fmtNumber, fmtDate ] = useFormat()" in var_data.hooks
    assert any(lib == "$/utils/i18n" for lib, _ in var_data.imports)
    priority, provider = var_data.app_wraps[0]
    assert priority == 58
    assert isinstance(provider, I18nProvider)


def test_number_and_date_share_one_hook():
    combined = Var.create([number(_num()), date(Var(_js_expr="state.day"))])
    var_data = combined._get_all_var_data()
    assert var_data is not None
    hooks = [h for h in var_data.hooks if "useFormat" in h]
    assert hooks == ["const [ fmtNumber, fmtDate ] = useFormat()"]


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


def test_formatting_without_plugin_raises():
    set_active_i18n_config(None)
    with pytest.raises(RuntimeError, match="requires the i18n plugin"):
        number(_num())
    with pytest.raises(RuntimeError, match="requires the i18n plugin"):
        date(Var(_js_expr="state.day"))
