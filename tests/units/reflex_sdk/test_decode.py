from __future__ import annotations

import datetime
import enum
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

import pytest
from reflex_sdk._decode import DecodeError, _decoder_for, decode


class Color(enum.Enum):
    """An enum to decode."""

    RED = "red"


@dataclass(frozen=True, kw_only=True)
class Inner:
    """A model nested in another."""

    value: int


@dataclass(frozen=True, kw_only=True)
class Outer:
    """A model with nested, list and optional fields."""

    name: str
    inner: Inner
    items: list[Inner] = field(default_factory=list)
    note: str | None = None


@dataclass(frozen=True, kw_only=True)
class Node:
    """A model that references itself."""

    children: list[Node]


@pytest.mark.parametrize(
    ("tp", "value", "expected"),
    [
        (str, "a", "a"),
        (int, 3, 3),
        (bool, True, True),
        (float, 1.5, 1.5),
        (float, 2, 2.0),
        (type(None), None, None),
        (Any, {"a": [1]}, {"a": [1]}),
        (
            uuid.UUID,
            "12345678-1234-5678-1234-567812345678",
            uuid.UUID("12345678-1234-5678-1234-567812345678"),
        ),
        (
            datetime.datetime,
            "2026-09-16T10:00:00Z",
            datetime.datetime(2026, 9, 16, 10, tzinfo=datetime.timezone.utc),
        ),
        (
            datetime.datetime,
            "2026-09-16T10:00:00.123456+00:00",
            datetime.datetime(
                2026, 9, 16, 10, 0, 0, 123456, tzinfo=datetime.timezone.utc
            ),
        ),
        (datetime.date, "2026-09-16", datetime.date(2026, 9, 16)),
        (Color, "red", Color.RED),
        (Literal["all"], "all", "all"),
        (list[int], [1, 2], [1, 2]),
        (list, [1, "a"], [1, "a"]),
        (dict[str, int], {"a": 1}, {"a": 1}),
        (dict[str, Any], {"a": [1]}, {"a": [1]}),
        (int | None, None, None),
        (int | None, 1, 1),
        (Literal["all"] | list[str], ["p"], ["p"]),
        (int | str, "a", "a"),
    ],
)
def test_decode_values(tp: Any, value: Any, expected: Any):
    assert decode(tp, value) == expected


@pytest.mark.parametrize(
    ("tp", "value", "message"),
    [
        (str, 1, "expected string, got int at $"),
        (int, True, "expected integer, got bool at $"),
        (int, 1.0, "expected integer, got float at $"),
        (bool, 1, "expected boolean, got int at $"),
        (float, True, "expected number, got bool at $"),
        (type(None), 0, "expected null, got int at $"),
        (uuid.UUID, "nope", "invalid UUID 'nope' at $"),
        (datetime.datetime, 5, "expected datetime, got int at $"),
        (Color, "blue", "invalid Color 'blue' at $"),
        (Literal["all"], "some", "expected one of ('all',), got 'some' at $"),
        (list[int], [1, "a"], "expected integer, got str at $[1]"),
        (list, {}, "expected array, got dict at $"),
        (dict[str, int], {"a": 1, "b": "c"}, "expected integer, got str at $.b"),
        (dict, [], "expected object, got list at $"),
        (
            list[dict[str, list[int]]],
            [{"a": [1]}, {"a": [2, None]}],
            "expected integer, got NoneType at $[1].a[1]",
        ),
        (
            int | str,
            [],
            (
                "matched no member of the union "
                "(expected integer, got list; expected string, got list) at $"
            ),
        ),
        (
            list[int] | str,
            [1, "a"],
            (
                "matched no member of the union "
                "(expected integer, got str at [1]; expected string, got list) at $"
            ),
        ),
        (
            int | str,
            None,
            (
                "matched no member of the union "
                "(expected integer, got NoneType; expected string, got NoneType) at $"
            ),
        ),
    ],
)
def test_decode_mismatch(tp: Any, value: Any, message: str):
    with pytest.raises(DecodeError) as exc_info:
        decode(tp, value)
    assert str(exc_info.value) == message


def test_decode_dataclass():
    decoded = decode(
        Outer,
        {
            "name": "app",
            "inner": {"value": 1},
            "items": [{"value": 2, "unknown": True}],
            "added_by_a_newer_server": 1,
        },
    )
    assert decoded == Outer(name="app", inner=Inner(value=1), items=[Inner(value=2)])


def test_decode_dataclass_missing_required_field():
    with pytest.raises(DecodeError) as exc_info:
        decode(Outer, {"name": "app", "inner": {}})
    assert str(exc_info.value) == "missing required field 'value' at $.inner"


def test_decode_dataclass_not_an_object():
    with pytest.raises(DecodeError) as exc_info:
        decode(Outer, {"name": "app", "inner": [], "items": [{"value": "x"}]})
    assert str(exc_info.value) == "expected Inner object, got list at $.inner"


def test_decode_dataclass_nested_error_path():
    with pytest.raises(DecodeError) as exc_info:
        decode(Outer, {"name": "app", "inner": {"value": 1}, "items": [{"value": "x"}]})
    assert str(exc_info.value) == "expected integer, got str at $.items[0].value"


def test_decode_self_referencing_dataclass():
    decoded = decode(Node, {"children": [{"children": []}]})
    assert decoded == Node(children=[Node(children=[])])


def test_decoders_are_cached():
    assert _decoder_for(list[Inner]) is _decoder_for(list[Inner])


def test_decode_unsupported_type():
    with pytest.raises(TypeError, match="cannot decode into"):
        decode(set[int], [])
