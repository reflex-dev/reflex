"""Tests for the rx.t translation var."""

import pytest
from reflex_base.vars.base import LiteralVar, Var
from reflex_i18n import I18nConfig, t
from reflex_i18n.component import I18nProvider
from reflex_i18n.config import set_active_i18n_config
from reflex_i18n.registry import MessageKey, clear_messages, collected_messages


@pytest.fixture(autouse=True)
def clean_registry():
    """Isolate the message registry and activate a config for ``t``.

    Yields:
        None
    """
    clear_messages()
    set_active_i18n_config(I18nConfig(locales=["en", "de"], default_locale="en"))
    yield
    clear_messages()
    set_active_i18n_config(None)


def test_t_simple_message():
    var = t("Hello")
    assert str(var) == '(t_("Hello", ({  })))'
    assert var._var_type is str


def test_t_interpolated_params():
    name_var = Var(_js_expr="state.name", _var_type=str)
    var = t("Hello {name}!", name=name_var)
    assert 't_("Hello {name}!"' in str(var)
    assert "state.name" in str(var)


def test_t_var_data():
    var = t("Hello")
    var_data = var._get_all_var_data()
    assert var_data is not None
    assert "const [ t_, tp_ ] = useTranslation()" in var_data.hooks
    assert any(lib == "$/utils/i18n" for lib, _ in var_data.imports)
    assert len(var_data.app_wraps) == 1
    priority, provider = var_data.app_wraps[0]
    assert priority == 58
    assert isinstance(provider, I18nProvider)


def test_t_context_key():
    var = t("Open", context="menu")
    assert '"menu\\u0004Open"' in str(var)


def test_t_plural():
    count_var = Var(_js_expr="state.count", _var_type=int)
    var = t("{count} item", plural="{count} items", count=count_var)
    js = str(var)
    assert js.startswith('(tp_("{count} item", "{count} items", state.count')
    # count is implicitly available for interpolation.
    assert '["count"] : state.count' in js


def test_t_plural_explicit_count_param_wins():
    var = t("{count} item", plural="{count} items", count=2, count_label="two")
    assert '["count"] : 2' in str(var)


def test_t_registers_messages():
    t("Hello")
    t("{count} item", plural="{count} items", count=1)
    t("Open", context="menu")
    assert collected_messages() == (
        MessageKey("Hello", None, None),
        MessageKey("{count} item", "{count} items", None),
        MessageKey("Open", None, "menu"),
    )


def test_t_deduplicates_messages():
    t("Hello")
    t("Hello")
    assert collected_messages() == (MessageKey("Hello", None, None),)


def test_t_in_fstring_keeps_var_data():
    var = LiteralVar.create(f"{t('Hello')} world")
    var_data = var._get_all_var_data()
    assert var_data is not None
    assert "const [ t_, tp_ ] = useTranslation()" in var_data.hooks
    assert len(var_data.app_wraps) == 1


def test_t_rejects_non_literal_message():
    state_var = Var(_js_expr="state.msg", _var_type=str)
    with pytest.raises(TypeError, match="literal string"):
        t(state_var)  # pyright: ignore[reportArgumentType]


def test_t_rejects_non_literal_plural():
    state_var = Var(_js_expr="state.msg", _var_type=str)
    with pytest.raises(TypeError, match="literal string"):
        t("{count} item", plural=state_var, count=1)  # pyright: ignore[reportArgumentType]


def test_t_plural_requires_count():
    with pytest.raises(ValueError, match="count and plural"):
        t("{count} item", plural="{count} items")


def test_t_count_requires_plural():
    with pytest.raises(ValueError, match="count and plural"):
        t("{count} item", count=1)
