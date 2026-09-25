"""Unit tests for reflex_base.utils.format."""

import pytest
from reflex_base import constants
from reflex_base.style import Style
from reflex_base.utils import format
from reflex_base.vars.base import Var

import reflex as rx


@pytest.mark.parametrize(
    ("prop", "formatted"),
    [
        ({"a": "red", "b": 1}, '({ ["a"] : "red", ["b"] : 1 })'),
        ({"a": Var(_js_expr="x")}, '({ ["a"] : x })'),
        (Style({"color": "red"}), '({ ["color"] : "red" })'),
    ],
)
def test_format_prop_dict(prop: dict, formatted: str):
    """Dict props format as JS object literals, keeping nested vars as JS.

    Args:
        prop: The dict prop to format.
        formatted: The expected formatted prop.
    """
    assert format.format_prop(prop) == formatted


def test_format_prop_dict_invalid_value():
    """A dict value with no JS representation raises a TypeError."""
    with pytest.raises(TypeError, match="Could not format prop"):
        format.format_prop({"a": object()})


def test_format_queue_events_dispatches_through_add_events():
    """The formatted callback calls addEvents and carries its imports."""
    var = format.format_queue_events(rx.console_log("hello"))
    js = str(var)
    assert js.startswith("() => {addEvents([")
    assert "queueEvents" not in js

    var_data = var._get_all_var_data()
    assert var_data is not None
    imports = dict(var_data.imports)
    context_imports = imports[f"$/{constants.Dirs.CONTEXTS_PATH}"]
    assert any(imp.tag == "addEvents" for imp in context_imports)
    state_imports = imports[f"$/{constants.Dirs.STATE_PATH}"]
    assert any(imp.tag == "ReflexEvent" for imp in state_imports)


def test_format_queue_events_empty():
    """No events formats to a null callback."""
    assert str(format.format_queue_events(None)) == "(() => null)"


def test_format_queue_events_args_spec():
    """The args spec names the callback parameters."""
    var = format.format_queue_events(
        rx.console_log("hello"),
        args_spec=lambda result: [result],
    )
    assert str(var).startswith("(_result) => {addEvents([")
