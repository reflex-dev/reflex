"""Tests for normalizing run state into JSON-compatible data.

Everything a handler leaves in `self` crosses this boundary on the way to the
store, so what it accepts is what a run can hold and what it refuses is what a
developer finds out about immediately rather than at a commit.
"""

import datetime
import uuid

import pytest
from pydantic import BaseModel

from reflex.workflow.serde import to_run_data


class Quote(BaseModel):
    """A typical typed value held in run state."""

    price: int
    vendor: str


def test_common_values_reduce_to_plain_data():
    """The types a handler actually holds survive the crossing."""
    reduced = to_run_data({
        "when": datetime.date(2026, 1, 1),
        "id": uuid.UUID(int=7),
        "quote": Quote(price=42, vendor="acme"),
        "tags": {"b", "a"},
        "pair": (1, 2),
    })
    assert reduced["when"] == "2026-01-01"
    assert reduced["id"] == "00000000-0000-0000-0000-000000000007"
    assert reduced["quote"] == {"price": 42, "vendor": "acme"}
    assert sorted(reduced["tags"]) == ["a", "b"]
    assert reduced["pair"] == [1, 2]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_a_float_json_cannot_hold_is_refused(value: float):
    """NaN and infinity are not JSON, whatever Python is willing to emit.

    Left alone they pass through memory and SQLite -- Python's decoder accepts
    the tokens its encoder produced -- and are rejected by Postgres JSONB at
    commit. That is a workflow that works in development and fails in
    production, on the store, with the offending value long gone from the
    traceback.
    """
    with pytest.raises(ValueError, match="JSON compliant"):
        to_run_data({"value": value})


def test_a_nested_non_finite_float_is_refused():
    """The check reaches values buried in state, not just top-level ones."""
    with pytest.raises(ValueError, match="JSON compliant"):
        to_run_data({"readings": [1.0, {"latest": float("nan")}]})


def test_a_circular_reference_is_refused():
    """State that points at itself cannot be written down."""
    loop: dict = {}
    loop["self"] = loop
    with pytest.raises(ValueError, match=r"[Cc]ircular"):
        to_run_data(loop)


def test_an_unserializable_object_is_refused():
    """A value no serializer handles fails here, not at the store."""
    with pytest.raises(TypeError):
        to_run_data({"handle": object()})


def test_decimal_is_refused_rather_than_silently_truncated():
    """Decimal("10.10") must never replay as 10.1.

    The serializer registry hands back a float, losing precision on exactly
    the type people reach for to avoid losing precision -- a silent money bug.
    Refusing at record time names the fix.
    """
    from decimal import Decimal

    with pytest.raises(TypeError, match="Decimal"):
        to_run_data({"amount": Decimal("10.10")})


def test_bytes_are_refused_rather_than_becoming_integer_lists():
    """Raw bytes stored as [114, 97, 119] never come back as bytes."""
    with pytest.raises(TypeError, match="base64"):
        to_run_data({"blob": b"raw"})
    with pytest.raises(TypeError, match="bytearray"):
        to_run_data({"blob": bytearray(b"raw")})
