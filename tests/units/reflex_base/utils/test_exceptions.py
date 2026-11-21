"""Tests for reflex_base.utils.exceptions."""

import pickle
from unittest import mock

import pytest
from reflex_base.utils.exceptions import (
    BrowserResultSerializationError,
    BrowserScriptError,
    ReflexError,
)


def test_base_var_shadows_inherited_var_error_is_deprecated():
    """Importing the removed shadowing error still works, with a deprecation warning."""
    with mock.patch("reflex_base.utils.console.deprecate") as deprecate:
        from reflex.utils.exceptions import BaseVarShadowsInheritedVarError

    assert issubclass(BaseVarShadowsInheritedVarError, ReflexError)
    assert issubclass(BaseVarShadowsInheritedVarError, NameError)
    deprecate.assert_called_once_with(
        feature_name="BaseVarShadowsInheritedVarError",
        reason="Nothing raises it: a substate may redeclare an inherited var.",
        deprecation_version="0.11.0",
        removal_version="1.0",
    )


@pytest.mark.parametrize(
    ("error_cls", "fields", "text"),
    [
        (
            BrowserScriptError,
            ("TypeError", "x is undefined", "at <anon>:1"),
            "TypeError: x is undefined",
        ),
        (
            BrowserResultSerializationError,
            ("", "The value is nested too deeply.", ""),
            "The value is nested too deeply.",
        ),
    ],
)
def test_browser_script_error_formats_and_pickles(
    error_cls: type[BrowserScriptError], fields: tuple[str, str, str], text: str
):
    """A browser script error reads like the console, and survives pickling.

    Args:
        error_cls: The error class.
        fields: Its name, message and stack.
        text: Its expected text.
    """
    error = error_cls(*fields)
    copy = pickle.loads(pickle.dumps(error))
    assert [
        (type(e), (e.name, e.message, e.stack), e.args, str(e)) for e in (error, copy)
    ] == [(error_cls, fields, fields, text)] * 2
