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
    SENTINEL_ESCAPE_PREFIX,
    _replace_non_finite_floats,
    json_dumps,
    orjson_dumps,
    orjson_dumps_socket,
    orjson_loads,
)

# orjson_dumps + orjson_loads round-trip


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


# socket.io kwarg compat (regression test for the bug that broke
# integration tests: socket.io calls dumps(data, separators=(',',':')))


def test_orjson_dumps_socket_accepts_separators_kwarg():
    out = orjson_dumps_socket({"a": 1}, separators=(",", ":"))
    assert out == '{"a":1}'


def test_orjson_dumps_socket_ignores_arbitrary_kwargs():
    out = orjson_dumps_socket([1, 2, 3], separators=(",", ":"), sort_keys=True)
    assert orjson_loads(out) == [1, 2, 3]


# non-finite float sentinels


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


# user strings colliding with a sentinel must be escaped, not revived


@pytest.mark.parametrize("sentinel", [NAN_SENTINEL, INF_SENTINEL, NEG_INF_SENTINEL])
def test_sentinel_string_value_is_escaped(sentinel):
    out = orjson_dumps_socket({"a": sentinel})
    assert orjson_loads(out) == {"a": SENTINEL_ESCAPE_PREFIX + sentinel}


def test_escape_prefixed_string_is_escaped_again():
    value = SENTINEL_ESCAPE_PREFIX + "user data"
    out = orjson_dumps_socket([value])
    assert orjson_loads(out) == [SENTINEL_ESCAPE_PREFIX + value]


@pytest.mark.parametrize(
    "value",
    [
        "nan",
        "__reflex_nan__ ",
        "__reflex_nan",
        "prefix__reflex_nan__",
        "__reflex_custom__",
        "__reflex",
    ],
)
def test_non_sentinel_string_unchanged(value):
    assert orjson_loads(orjson_dumps_socket([value])) == [value]


def test_walker_escapes_sentinel_string():
    """The walker escapes sentinel strings, covering the stdlib fallback too."""
    assert (
        _replace_non_finite_floats(NAN_SENTINEL)
        == SENTINEL_ESCAPE_PREFIX + NAN_SENTINEL
    )


def test_sentinel_string_inside_dataclass_field():
    @dataclasses.dataclass
    class Message:
        text: str

    out = orjson_dumps_socket({"m": Message(NAN_SENTINEL)})
    assert orjson_loads(out) == {"m": {"text": SENTINEL_ESCAPE_PREFIX + NAN_SENTINEL}}


# copy-on-write walker behavior


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


# format compatibility with the existing json_dumps


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


# native scalar subclasses serialize as their base value


class _IntSubclass(int):
    pass


class _StrSubclass(str):
    pass


class _FloatSubclass(float):
    pass


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (_IntSubclass(25), 25),
        (_IntSubclass(0), 0),
        (_StrSubclass("hello"), "hello"),
        (_StrSubclass(""), ""),
        (_FloatSubclass(1.5), 1.5),
    ],
)
def test_native_subclass_serializes_to_base_value(value, expected):
    assert orjson_loads(orjson_dumps_socket({"v": value})) == {"v": expected}


@pytest.mark.parametrize(
    "value",
    [_IntSubclass(25), _StrSubclass("hello"), _FloatSubclass(1.5)],
)
def test_native_subclass_matches_json_dumps(value):
    assert json.loads(orjson_dumps_socket({"v": value})) == json.loads(
        json_dumps({"v": value})
    )


def test_int_subclass_inside_dataclass_field():
    @dataclasses.dataclass
    class Pagination:
        page: int
        size: int

    out = orjson_dumps_socket({"p": Pagination(_IntSubclass(3), _IntSubclass(25))})
    assert orjson_loads(out) == {"p": {"page": 3, "size": 25}}


def test_datetime_uses_space_separator_not_iso_t():
    """Regression: orjson natively emits 'T'-separated datetimes; we route
    them through ``serializers.serialize_datetime`` to keep the existing
    space-separated format consumed by the JS side.
    """
    dt = datetime.datetime(2026, 4, 25, 10, 30, 45)
    out = orjson_dumps_socket({"dt": dt})
    assert orjson_loads(out) == {"dt": "2026-04-25 10:30:45"}


# non-string dict keys


def test_int_dict_keys_coerced_to_strings():
    out = orjson_dumps_socket({1: "a", 2: "b"})
    assert orjson_loads(out) == {"1": "a", "2": "b"}


# unknown-type fallback


def test_unknown_type_serializes_to_null():
    """Types without a registered serializer return None from
    ``serializers.serialize`` and end up as JSON null -- matches stdlib
    ``json.dumps(default=serialize)`` behavior.
    """

    class Unknown:
        pass

    out = orjson_dumps_socket({"x": Unknown()})
    assert orjson_loads(out) == {"x": None}


@pytest.fixture
def no_orjson(monkeypatch: pytest.MonkeyPatch):
    """Simulate orjson not being installed.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    from reflex_base.utils import format as format_module

    monkeypatch.setattr(format_module, "orjson", None)


def test_fallback_emits_bare_non_finite_tokens(no_orjson):
    """Without orjson, non-finite floats stay as bare stdlib tokens; the
    frontend's bare-token rewriter restores them, so no walk is needed.
    """
    assert (
        orjson_dumps_socket([1.0, float("nan"), float("inf")]) == "[1.0,NaN,Infinity]"
    )


def test_fallback_uses_compact_separators(no_orjson):
    assert orjson_dumps_socket({"a": 1, "b": [2, 3]}) == '{"a":1,"b":[2,3]}'


def test_fallback_skips_walk_on_clean_payload(no_orjson, monkeypatch):
    """The walker must not run when the output contains no sentinel prefix."""
    from reflex_base.utils import format as format_module

    def _fail(_obj):
        pytest.fail("walker ran on a clean payload")

    monkeypatch.setattr(format_module, "_replace_non_finite_floats", _fail)
    out = orjson_dumps_socket({"rows": [{"id": 1, "name": "x"}] * 5, "f": 1.5})
    assert json.loads(out) == {"rows": [{"id": 1, "name": "x"}] * 5, "f": 1.5}


@pytest.mark.parametrize("sentinel", [NAN_SENTINEL, INF_SENTINEL, NEG_INF_SENTINEL])
def test_fallback_escapes_colliding_strings(no_orjson, sentinel):
    out = orjson_dumps_socket({"a": sentinel})
    assert json.loads(out) == {"a": SENTINEL_ESCAPE_PREFIX + sentinel}


def test_fallback_collision_walk_sentinelizes_non_finite_floats(no_orjson):
    """When a collision triggers the walk, NaN in the same payload becomes a
    sentinel too, keeping the re-dumped output strict JSON.
    """
    out = orjson_dumps_socket({"s": NAN_SENTINEL, "f": float("nan")})
    assert json.loads(out) == {
        "s": SENTINEL_ESCAPE_PREFIX + NAN_SENTINEL,
        "f": NAN_SENTINEL,
    }


def test_orjson_dumps_indent_4_falls_back_to_stdlib():
    """Orjson only supports 2-space indent; other widths must not be
    silently coerced to 2.
    """
    out = orjson_dumps({"a": 1}, indent=4)
    assert out == json.dumps({"a": 1}, indent=4, ensure_ascii=False)


def test_orjson_dumps_indent_2_matches_orjson():
    import orjson as orjson_module

    assert (
        orjson_dumps({"a": 1}, indent=2)
        == orjson_module.dumps({"a": 1}, option=orjson_module.OPT_INDENT_2).decode()
    )


def test_orjson_dumps_type_error_fallback_preserves_kwargs():
    """Orjson raises TypeError for ints > 64-bit; the stdlib fallback must
    keep sort_keys/indent instead of dropping them.
    """
    out = orjson_dumps({"b": 2**70, "a": 1}, sort_keys=True)
    assert out.index('"a"') < out.index('"b"')


def test_orjson_skips_walk_on_clean_payload(monkeypatch: pytest.MonkeyPatch):
    """A payload without None/NaN/collisions must serialize in one pass."""
    from reflex_base.utils import format as format_module

    def _fail(_obj):
        pytest.fail("walker ran on a clean payload")

    monkeypatch.setattr(format_module, "_replace_non_finite_floats", _fail)
    payload = {"rows": [{"id": 1, "name": "x", "balance": 1.5}] * 3}
    assert orjson_loads(orjson_dumps_socket(payload)) == payload


def test_orjson_none_values_stay_null():
    """None triggers the verification walk but must still serialize as null."""
    payload = {"a": None, "b": [None, 1.0], "c": "x"}
    assert orjson_loads(orjson_dumps_socket(payload)) == payload


def test_orjson_null_substring_in_string_is_safe():
    """A user string containing 'null' may trigger the walk but not corruption."""
    payload = {"msg": "the null hypothesis", "n": 1}
    assert orjson_loads(orjson_dumps_socket(payload)) == payload


def test_orjson_none_and_nan_together():
    """Real None stays null while NaN in the same payload becomes a sentinel."""
    out = orjson_dumps_socket({"a": None, "b": float("nan")})
    assert orjson_loads(out) == {"a": None, "b": NAN_SENTINEL}


# real packet shape: sentinels inside StateUpdate must survive every fallback


def _wire_packet(delta_values: dict) -> list:
    from reflex.state import StateUpdate

    return ["event", StateUpdate(delta={"state": delta_values})]


def _delta_values(wire: str) -> dict:
    return json.loads(wire)[1]["delta"]["state"]


def test_fallback_escapes_collision_inside_state_update(no_orjson):
    """Sentinel-colliding strings nested in a StateUpdate must be escaped by
    the stdlib fallback, not shipped raw for the JS reviver to corrupt.
    """
    wire = orjson_dumps_socket(
        _wire_packet({"v": NAN_SENTINEL, "e": SENTINEL_ESCAPE_PREFIX + "x"})
    )
    assert _delta_values(wire) == {
        "v": SENTINEL_ESCAPE_PREFIX + NAN_SENTINEL,
        "e": SENTINEL_ESCAPE_PREFIX + SENTINEL_ESCAPE_PREFIX + "x",
    }


def test_fallback_nan_inside_state_update_with_collision(no_orjson):
    """When a collision forces the walking re-dump, NaN nested in the
    StateUpdate becomes a sentinel so the output stays strict JSON.
    """
    wire = orjson_dumps_socket(_wire_packet({"v": NAN_SENTINEL, "f": float("nan")}))
    assert _delta_values(wire) == {
        "v": SENTINEL_ESCAPE_PREFIX + NAN_SENTINEL,
        "f": NAN_SENTINEL,
    }


def test_type_error_fallback_escapes_collision_inside_state_update():
    """Orjson raises TypeError for >64-bit ints; the stdlib fallback must
    still escape colliding strings nested in the StateUpdate.
    """
    wire = orjson_dumps_socket(_wire_packet({"big": 2**70, "v": NAN_SENTINEL}))
    assert _delta_values(wire) == {
        "big": 2**70,
        "v": SENTINEL_ESCAPE_PREFIX + NAN_SENTINEL,
    }
