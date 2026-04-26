"""Tests for orjson-based serializers in reflex_base.utils.format.

Covers ``orjson_dumps``, ``orjson_loads``, ``orjson_dumps_socket`` and the
``_replace_non_finite_floats`` walker.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
from decimal import Decimal
from enum import Enum
from pathlib import Path
from uuid import UUID

import pytest

# Skip the entire module if orjson is not installed -- the helpers have
# stdlib fallbacks but these tests target the orjson code path.
pytest.importorskip("orjson")

from reflex_base.style import Style
from reflex_base.utils.format import (
    INF_SENTINEL,
    NAN_SENTINEL,
    NEG_INF_SENTINEL,
    _replace_non_finite_floats,
    json_dumps,
    orjson_dumps,
    orjson_dumps_socket,
    orjson_loads,
)

# --- orjson_dumps + orjson_loads round-trip ---


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        0,
        -1,
        1.5,
        "hello",
        "",
        [],
        {},
        [1, 2, 3],
        {"a": 1, "b": [2, 3]},
        {"nested": {"deep": {"value": [1, 2, 3]}}},
    ],
)
def test_orjson_round_trip(value):
    assert orjson_loads(orjson_dumps(value)) == value


# --- socket.io kwarg compat (regression test for the bug that broke
#     integration tests: socket.io calls dumps(data, separators=(',',':')))


def test_orjson_dumps_socket_accepts_separators_kwarg():
    out = orjson_dumps_socket({"a": 1}, separators=(",", ":"))
    assert out == '{"a":1}'


def test_orjson_dumps_socket_ignores_arbitrary_kwargs():
    out = orjson_dumps_socket([1, 2, 3], separators=(",", ":"), sort_keys=True)
    assert orjson_loads(out) == [1, 2, 3]


# --- non-finite float sentinels ---


def test_nan_top_level():
    assert orjson_dumps_socket(float("nan")) == f'"{NAN_SENTINEL}"'


def test_inf_top_level():
    assert orjson_dumps_socket(float("inf")) == f'"{INF_SENTINEL}"'


def test_neg_inf_top_level():
    assert orjson_dumps_socket(float("-inf")) == f'"{NEG_INF_SENTINEL}"'


def test_nan_in_list():
    out = orjson_dumps_socket([1.0, float("nan"), 2.0])
    assert orjson_loads(out) == [1.0, NAN_SENTINEL, 2.0]


def test_nan_in_dict():
    out = orjson_dumps_socket({"x": float("nan"), "y": 1.0})
    assert orjson_loads(out) == {"x": NAN_SENTINEL, "y": 1.0}


def test_non_finite_floats_deeply_nested():
    out = orjson_dumps_socket({"a": {"b": [{"c": float("nan")}, float("inf")]}})
    assert orjson_loads(out) == {"a": {"b": [{"c": NAN_SENTINEL}, INF_SENTINEL]}}


def test_all_three_sentinels():
    out = orjson_dumps_socket([float("nan"), float("inf"), float("-inf")])
    assert orjson_loads(out) == [NAN_SENTINEL, INF_SENTINEL, NEG_INF_SENTINEL]


def test_nan_inside_dataclass_field():
    """Dataclass fields with NaN must still get the sentinel."""

    @dataclasses.dataclass
    class Point:
        x: float
        y: float

    out = orjson_dumps_socket({"p": Point(float("nan"), 1.0)})
    assert orjson_loads(out) == {"p": {"x": NAN_SENTINEL, "y": 1.0}}


# --- copy-on-write walker behavior ---


def test_walker_returns_unchanged_dict_as_is():
    obj = {"a": 1, "b": [1, 2, 3], "c": {"d": "hi"}}
    assert _replace_non_finite_floats(obj) is obj


def test_walker_returns_unchanged_list_as_is():
    obj = [1, 2.0, "x", {"k": "v"}]
    assert _replace_non_finite_floats(obj) is obj


def test_walker_returns_unchanged_tuple_as_is():
    obj = (1, 2.0, "x")
    assert _replace_non_finite_floats(obj) is obj


def test_walker_preserves_unchanged_subtree_when_sibling_changes():
    inner = {"safe": 1.0, "also_safe": [1, 2]}
    outer = {"a": inner, "b": float("nan")}
    result = _replace_non_finite_floats(outer)
    assert result is not outer
    assert result["a"] is inner
    assert result["b"] == NAN_SENTINEL


def test_walker_converts_modified_tuple_to_list():
    t = (1, float("nan"), "x")
    assert _replace_non_finite_floats(t) == [1, NAN_SENTINEL, "x"]


def test_walker_passes_through_unknown_types():
    class Sentinel:
        pass

    s = Sentinel()
    assert _replace_non_finite_floats(s) is s


# --- format compatibility with the existing json_dumps ---


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        0,
        1,
        1.5,
        "hello",
        [1, 2, 3],
        {"a": 1, "b": "two"},
        {"nested": {"deep": [1, "two", None]}},
        datetime.datetime(2026, 4, 25, 10, 30, 45),
        datetime.datetime(2026, 4, 25, 10, 30, 45, 123456),
        datetime.datetime(2026, 4, 25, 10, 30, 45, tzinfo=datetime.timezone.utc),
        datetime.date(2026, 4, 25),
        datetime.time(10, 30, 45),
        datetime.timedelta(days=1, seconds=1, microseconds=1),
        Decimal("3.14"),
        UUID("12345678-1234-5678-1234-567812345678"),
        Path("/tmp/foo"),
    ],
)
def test_socket_output_matches_json_dumps_for_finite_inputs(value):
    """For inputs without NaN/Inf, ``orjson_dumps_socket`` must produce
    a payload that decodes to the same Python object as ``json_dumps``.
    """
    socket_out = orjson_dumps_socket(value)
    json_out = json_dumps(value)
    assert json.loads(socket_out) == json.loads(json_out)


def test_enum_value_serialized_consistently():
    class Color(Enum):
        RED = "red"
        BLUE = "blue"

    assert json.loads(orjson_dumps_socket({"c": Color.RED})) == json.loads(
        json_dumps({"c": Color.RED})
    )


def test_dict_subclass_style_serializes_equivalently():
    """``Style`` is a dict subclass; both paths must agree on the output."""
    style = Style({"color": "red", "size": 12})
    assert json.loads(orjson_dumps_socket(style)) == json.loads(json_dumps(style))


def test_datetime_uses_space_separator_not_iso_t():
    """Regression: orjson natively emits 'T'-separated datetimes; we route
    them through ``serializers.serialize_datetime`` to keep the existing
    space-separated format consumed by the JS side.
    """
    dt = datetime.datetime(2026, 4, 25, 10, 30, 45)
    out = orjson_dumps_socket({"dt": dt})
    assert orjson_loads(out) == {"dt": "2026-04-25 10:30:45"}


# --- non-string dict keys ---


def test_int_dict_keys_coerced_to_strings():
    out = orjson_dumps_socket({1: "a", 2: "b"})
    assert orjson_loads(out) == {"1": "a", "2": "b"}


# --- unknown-type fallback ---


def test_unknown_type_serializes_to_null():
    """Types without a registered serializer return None from
    ``serializers.serialize`` and end up as JSON null -- matches stdlib
    ``json.dumps(default=serialize)`` behavior.
    """

    class Unknown:
        pass

    out = orjson_dumps_socket({"x": Unknown()})
    assert orjson_loads(out) == {"x": None}
