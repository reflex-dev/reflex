"""Tests for the rx.t translation var."""

import json
import shutil
import subprocess

import pytest
from reflex_base.vars.base import LiteralVar, Var
from reflex_i18n import I18nConfig, t
from reflex_i18n.component import I18nProvider
from reflex_i18n.config import set_active_i18n_config
from reflex_i18n.registry import (
    MessageKey,
    clear_messages,
    collected_messages,
    untranslated_messages,
)


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


def test_t_empty_context_is_no_context():
    t("Hello", context="")
    t("Hello")
    assert collected_messages() == (MessageKey("Hello", None, None),)
    with pytest.raises(ValueError, match="either singular or plural"):
        t("Hello", plural="Hellos", count=1, context="")


def test_t_rejects_singular_and_plural_of_same_message():
    t("item")
    with pytest.raises(ValueError, match="either singular or plural"):
        t("item", plural="items", count=1)
    # A context makes it a distinct gettext entry.
    t("item", plural="items", count=1, context="cart")


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


def test_t_rejects_non_literal_context():
    state_var = Var(_js_expr="state.ctx", _var_type=str)
    with pytest.raises(TypeError, match="literal string"):
        t("item", context=state_var)  # pyright: ignore[reportArgumentType]


def test_t_plural_requires_count():
    with pytest.raises(ValueError, match="count and plural"):
        t("{count} item", plural="{count} items")


def test_t_count_requires_plural():
    with pytest.raises(ValueError, match="count and plural"):
        t("{count} item", count=1)


def test_t_without_plugin_renders_source_text():
    # A library's rx.t still builds in an app that does not translate.
    set_active_i18n_config(None)
    var = t("Hello")
    assert str(var) == '"Hello"'
    assert var._get_all_var_data() is None

    name_var = Var(_js_expr="state.name", _var_type=str)
    var = t("Hello {name}!", name=name_var)
    assert str(var) == (
        "(((message, plural, count, params) => "
        "(plural !== null && count != 1 ? plural : message)"
        ".replace(/\\{(\\w+)\\}/g, (match, name) => "
        "name in params ? String(params[name]) : match))"
        '("Hello {name}!", null, null, ({ ["name"] : state.name })))'
    )
    # No translation hook and no provider: only the params' own var data.
    assert var._get_all_var_data() is None

    assert (
        collected_messages()
        == untranslated_messages()
        == (
            MessageKey("Hello"),
            MessageKey("Hello {name}!"),
        )
    )


@pytest.mark.skipif(shutil.which("node") is None, reason="node missing")
def test_t_without_plugin_interpolates_like_the_runtime():
    set_active_i18n_config(None)
    expressions = [
        t("Hello {name}!", name="Ada"),
        t("{count} item", plural="{count} items", count=1),
        t("{count} item", plural="{count} items", count=2),
        t("{count} file", plural="{count} files", count=0, context="disk"),
        t("{known} and {unknown}", known=True),
    ]
    script = (
        f"process.stdout.write(JSON.stringify([{', '.join(map(str, expressions))}]))"
    )
    result = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=True
    )
    assert json.loads(result.stdout) == [
        "Hello Ada!",
        "1 item",
        "2 items",
        "0 files",
        "true and {unknown}",
    ]


def test_t_with_plugin_records_nothing_untranslated():
    t("Hello")
    assert untranslated_messages() == ()
