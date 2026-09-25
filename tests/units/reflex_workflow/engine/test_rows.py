"""Tests for reflex_workflow.engine.rows, which addresses and diffs workflow rows.

These need no database: they are about the forms a primary key takes between the
row it identifies and the jsonb columns that point at it.
"""

from __future__ import annotations

import datetime
import decimal
import json
import uuid
from typing import Any

import pytest
from reflex_workflow import Workflow, step
from reflex_workflow.engine import rows
from sqlalchemy import DateTime, LargeBinary, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    """Declarative base for the test tables."""


class Unsaid(TypeDecorator):
    """A column type that does not say what Python value it holds."""

    impl = String
    cache_ok = True

    @property
    def python_type(self) -> type:
        """Refuse to say, as a type of one's own may.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError


class Shapes(Base):
    """One column of every type a key may be, to read the stored forms back through."""

    __tablename__ = "wf_rows_shapes"

    ident: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    moment: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    day: Mapped[datetime.date] = mapped_column()
    clock: Mapped[datetime.time] = mapped_column()
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2))
    blob: Mapped[bytes] = mapped_column(LargeBinary)
    name: Mapped[str] = mapped_column(String(16))
    count: Mapped[int] = mapped_column()
    private: Mapped[str] = mapped_column(Unsaid())


class Pair(Base, Workflow):
    """A run keyed by two columns, one of which json has no form of."""

    __tablename__ = "wf_rows_pair"

    tenant: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def work(self):
        """Record and stop."""
        self.status = "done"


MOMENT = datetime.datetime(2026, 9, 25, 14, 30, tzinfo=datetime.timezone.utc)
IDENT = uuid.UUID("4b1f2c3d-5e6a-4b8c-9d0e-1f2a3b4c5d6e")

# Every key type json has no form of, the column that holds it, and what the
# engine stores in its place.
BEYOND_JSON: list[tuple[str, Any, Any]] = [
    ("ident", IDENT, "4b1f2c3d-5e6a-4b8c-9d0e-1f2a3b4c5d6e"),
    ("moment", MOMENT, "2026-09-25T14:30:00+00:00"),
    ("day", datetime.date(2026, 9, 25), "2026-09-25"),
    ("clock", datetime.time(14, 30, 5), "14:30:05"),
    ("amount", decimal.Decimal("12.34"), "12.34"),
    ("blob", b"\x00\xff", "00ff"),
]


@pytest.mark.parametrize("value", [7, -1, "abc", 1.5, True, None])
def test_a_key_json_holds_is_stored_as_it_stands(value):
    assert rows.json_pk([value]) == [value]


@pytest.mark.parametrize(("column", "value", "stored"), BEYOND_JSON)
def test_a_key_json_has_no_form_of_is_stored_as_text(column, value, stored):
    assert rows.json_pk([value]) == [stored]
    # What is stored has to survive the trip through the jsonb column itself.
    assert json.loads(json.dumps(rows.json_pk([value]))) == [stored]


@pytest.mark.parametrize(("column", "value", "stored"), BEYOND_JSON)
def test_a_stored_key_reads_back_as_its_own_column_compares(column, value, stored):
    assert rows.loaded_key(Shapes.__table__.c[column], stored) == value


@pytest.mark.parametrize(("column", "value"), [("name", "abc"), ("count", 7)])
def test_a_key_json_holds_reads_back_untouched(column, value):
    assert rows.loaded_key(Shapes.__table__.c[column], value) == value


def test_a_column_that_will_not_say_what_it_holds_keeps_what_was_stored():
    assert rows.loaded_key(Shapes.__table__.c.private, "as it stood") == "as it stood"


def test_a_key_the_engine_cannot_store_is_refused_by_name():
    class Opaque:
        """A key type with no form the engine knows."""

    with pytest.raises(TypeError, match="cannot be a Opaque"):
        rows.json_pk([Opaque()])


def test_a_composite_key_is_stored_and_read_back_column_by_column():
    stored = rows.json_pk([IDENT, 7])
    assert stored == ["4b1f2c3d-5e6a-4b8c-9d0e-1f2a3b4c5d6e", 7]
    assert [
        clause.right.value  # pyright: ignore[reportAttributeAccessIssue]
        for clause in rows.pk_filter(Pair, stored)
    ] == [IDENT, 7]


def test_a_key_straight_from_the_database_needs_no_reading_back():
    # A claim hands back what the columns hold, which is already what they compare
    # against; only a pointer that went through jsonb has to be read back.
    assert [
        clause.right.value  # pyright: ignore[reportAttributeAccessIssue]
        for clause in rows.pk_filter(Pair, [IDENT, 7])
    ] == [IDENT, 7]


def test_a_rows_own_key_is_read_in_key_order():
    assert rows.pk_of(Pair(tenant=IDENT, number=7)) == [IDENT, 7]
