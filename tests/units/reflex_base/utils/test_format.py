"""Unit tests for reflex_base.utils.format."""

import datetime
import enum
import json
import math
import uuid

import pytest
from reflex_base import constants
from reflex_base.utils import format

import reflex as rx


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


class _Color(enum.Enum):
    RED = "red"


_WIRE_PAYLOADS = [
    {"big": 2**100, "neg": -(2**70), "nested": [[2**64], {"k": 2**65}]},
    {"f": [math.nan, math.inf, -math.inf, 0.1, 1e22, -0.0]},
    {"u": "café 😀", "q": '"\\\n'},
    {"s": "__reflex_nan__", "e": "__reflex_esc__x", "n": "NaN"},
    {2: "int key", 1.5: "float key", True: "bool key", None: "null key"},
    {"enum": _Color.RED, "uuid": uuid.UUID(int=1), "date": datetime.date(2024, 1, 2)},
    {"set": {1}, "tuple": (1, 2), "none": None, "empty": [{}, []]},
]


@pytest.mark.parametrize("payload", _WIRE_PAYLOADS)
def test_json_dumps_compact_yjson_matches_stdlib(payload, monkeypatch):
    """The yjson wire path writes the same JSON as the stdlib path."""
    pytest.importorskip("yjson")
    native = format.json_dumps(payload, separators=(",", ":"))
    monkeypatch.setattr(format, "yjson", None)
    assert native == format.json_dumps(payload, separators=(",", ":"))


def test_json_dumps_compact_yjson_escapes_lone_surrogates():
    """The yjson path escapes a lone surrogate, keeping the packet UTF-8 encodable."""
    pytest.importorskip("yjson")
    out = format.json_dumps({"s": "\ud800"}, separators=(",", ":"))
    assert out == '{"s":"\\ud800"}'
    assert json.loads(out) == {"s": "\ud800"}


def test_json_dumps_compact_yjson_custom_default(monkeypatch):
    """A caller-supplied default is used by the yjson path."""
    pytest.importorskip("yjson")
    payload = {"value": object()}
    out = format.json_dumps(payload, separators=(",", ":"), default=lambda _: "x")
    assert out == '{"value":"x"}'
    monkeypatch.setattr(format, "yjson", None)
    assert out == format.json_dumps(
        payload, separators=(",", ":"), default=lambda _: "x"
    )


def test_json_dumps_compact_yjson_small_floats_round_trip():
    """The shortest float repr of the yjson path parses to the same values."""
    pytest.importorskip("yjson")
    payload = [1e-7, 5e-324, 1.7976931348623157e308]
    assert json.loads(format.json_dumps(payload, separators=(",", ":"))) == payload
