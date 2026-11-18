"""Tests for starting a run keyed on one column.

The starts run against a real Postgres: set REFLEX_TEST_POSTGRES to a
postgresql:// URL for a database the tests may wipe.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from reflex_workflow import RunConflict, Workflow, connect_workflows, step
from reflex_workflow.engine import handles
from sqlalchemy import Index, String, UniqueConstraint, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

URL = os.environ.get("REFLEX_TEST_POSTGRES", "")
ASYNC_URL = URL.replace("postgresql://", "postgresql+psycopg://", 1)

needs_postgres = pytest.mark.skipif(
    not URL, reason="set REFLEX_TEST_POSTGRES to test against Postgres"
)
in_module_loop = pytest.mark.asyncio(loop_scope="module")


class Base(DeclarativeBase):
    """The tables these tests declare."""


class Onboarding(Base, Workflow):
    """A run keyed on the event that started it, with other unique keys beside it."""

    __tablename__ = "handles_onboarding"
    __table_args__ = (
        UniqueConstraint("team", "seat", name="uq_handles_onboarding_seat"),
        Index("ix_handles_onboarding_note", "note"),
        Index("ix_handles_onboarding_ref", "ref", unique=True),
        Index(
            "ix_handles_onboarding_slot",
            "slot",
            unique=True,
            postgresql_where=text("slot <> ''"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String, unique=True)
    trigger_key: Mapped[str | None] = mapped_column(String, unique=True, default=None)
    team: Mapped[str] = mapped_column(String, default=lambda: uuid.uuid4().hex)
    seat: Mapped[int] = mapped_column(default=0)
    note: Mapped[str] = mapped_column(String, default="")
    ref: Mapped[str] = mapped_column(String, default=lambda: uuid.uuid4().hex)
    slot: Mapped[str] = mapped_column(String, default="")

    @step
    async def welcome(self):
        """Do nothing; only the start is under test."""
        return


class Seat(Base, Workflow):
    """A run with a composite primary key."""

    __tablename__ = "handles_seat"

    team: Mapped[str] = mapped_column(String, primary_key=True)
    seat: Mapped[int] = mapped_column(primary_key=True)

    @step
    async def go(self):
        """Do nothing."""
        return


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def workflows() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Fresh tables, addressed without a worker.

    Yields:
        A session factory for the test database.
    """
    engine = create_async_engine(ASYNC_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with connect_workflows(factory):
        yield factory
    await engine.dispose()


def _onboarding(**columns: object) -> Onboarding:
    columns.setdefault("user_id", f"u-{uuid.uuid4().hex}")
    columns.setdefault("trigger_key", uuid.uuid4().hex)
    return Onboarding(**columns)


KEYED = {"key": Onboarding.trigger_key}


@needs_postgres
@in_module_loop
@pytest.mark.usefixtures("workflows")
async def test_a_repeat_of_the_key_returns_false():
    key = uuid.uuid4().hex
    first = _onboarding(trigger_key=key)
    assert await first.start(Onboarding.welcome, **KEYED) is True
    assert first.id is not None

    # A resend: the same key, whatever else the row says.
    resend = _onboarding(trigger_key=key)
    assert await resend.start(Onboarding.welcome, **KEYED) is False
    assert resend.id is None


@needs_postgres
@in_module_loop
@pytest.mark.usefixtures("workflows")
async def test_a_clash_on_another_unique_column_raises_run_conflict():
    user = f"u-{uuid.uuid4().hex}"
    assert await _onboarding(user_id=user).start(Onboarding.welcome, **KEYED)

    late = _onboarding(user_id=user)
    with pytest.raises(RunConflict) as raised:
        await late.start(Onboarding.welcome, **KEYED)
    assert raised.value.constraint == "handles_onboarding_user_id_key"
    assert str(raised.value) == (
        "the row clashes with an existing one on handles_onboarding_user_id_key"
    )
    assert late.id is None


@needs_postgres
@in_module_loop
@pytest.mark.usefixtures("workflows")
async def test_a_clash_on_a_multi_column_constraint_names_it():
    team = uuid.uuid4().hex
    assert await _onboarding(team=team).start(Onboarding.welcome, **KEYED)

    with pytest.raises(RunConflict) as raised:
        await _onboarding(team=team).start(Onboarding.welcome, **KEYED)
    assert raised.value.constraint == "uq_handles_onboarding_seat"


@needs_postgres
@in_module_loop
@pytest.mark.usefixtures("workflows")
async def test_an_empty_nullable_key_never_counts_as_a_repeat():
    assert await _onboarding(trigger_key=None).start(Onboarding.welcome, **KEYED)
    assert await _onboarding(trigger_key=None).start(Onboarding.welcome, **KEYED)


@needs_postgres
@in_module_loop
@pytest.mark.usefixtures("workflows")
async def test_without_key_any_clash_returns_false():
    user = f"u-{uuid.uuid4().hex}"
    assert await _onboarding(user_id=user).start(Onboarding.welcome) is True
    assert await _onboarding(user_id=user).start(Onboarding.welcome) is False


@needs_postgres
@in_module_loop
@pytest.mark.usefixtures("workflows")
async def test_a_single_column_primary_key_is_a_key():
    row = _onboarding()
    assert await row.start(Onboarding.welcome, key=Onboarding.id) is True
    again = _onboarding(id=row.id)
    assert await again.start(Onboarding.welcome, key=Onboarding.id) is False


@needs_postgres
@in_module_loop
@pytest.mark.usefixtures("workflows")
async def test_a_unique_index_is_a_key():
    ref = uuid.uuid4().hex
    assert await _onboarding(ref=ref).start(Onboarding.welcome, key=Onboarding.ref)
    repeat = _onboarding(ref=ref)
    assert await repeat.start(Onboarding.welcome, key=Onboarding.ref) is False

    # The trigger key is then just another unique column.
    clash = _onboarding(trigger_key=repeat.trigger_key)
    assert await clash.start(Onboarding.welcome, **KEYED)
    with pytest.raises(RunConflict) as raised:
        await _onboarding(trigger_key=repeat.trigger_key).start(
            Onboarding.welcome, key=Onboarding.ref
        )
    assert raised.value.constraint == "handles_onboarding_trigger_key_key"


def test_key_names_the_column_it_resolves_to():
    table = Onboarding.__table__
    assert handles.key_column(Onboarding, Onboarding.trigger_key) is table.c.trigger_key
    assert handles.key_column(Onboarding, Onboarding.id) is table.c.id
    assert handles.key_column(Onboarding, Onboarding.ref) is table.c.ref


def _refusal(cls: type[Workflow], key: object) -> str:
    with pytest.raises((TypeError, ValueError)) as raised:
        handles.key_column(cls, key)  # pyright: ignore[reportArgumentType]
    return f"{type(raised.value).__name__}: {raised.value}"


def test_key_must_be_one_unique_column_of_the_row():
    not_unique = "which is not unique on its own; give it unique=True."
    assert _refusal(Onboarding, Onboarding.note) == (
        f"ValueError: key= names Onboarding.note, {not_unique}"
    )
    assert _refusal(Onboarding, Onboarding.team) == (
        f"ValueError: key= names Onboarding.team, {not_unique}"
    )
    assert _refusal(Onboarding, Onboarding.slot) == (
        f"ValueError: key= names Onboarding.slot, {not_unique}"
    )
    assert _refusal(Seat, Seat.team) == (
        f"ValueError: key= names Seat.team, {not_unique}"
    )
    assert _refusal(Onboarding, "trigger_key") == (
        "TypeError: key= must be one column of Onboarding, not 'trigger_key'."
    )
    assert _refusal(Onboarding, Seat.team) == (
        f"TypeError: key= must be one column of Onboarding, not {Seat.team!r}."
    )
