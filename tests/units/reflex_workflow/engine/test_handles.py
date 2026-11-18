"""Tests for starting a run keyed on one column, against a real Postgres.

Set REFLEX_TEST_POSTGRES to a postgresql:// URL for a database the tests may wipe.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

URL = os.environ.get("REFLEX_TEST_POSTGRES", "")
if not URL:
    pytest.skip(
        "set REFLEX_TEST_POSTGRES to test against Postgres", allow_module_level=True
    )
ASYNC_URL = URL.replace("postgresql://", "postgresql+psycopg://", 1)

in_module_loop = pytest.mark.asyncio(loop_scope="module")

from reflex_workflow import RunConflict, Workflow, connect_workflows, step  # noqa: E402
from reflex_workflow.engine import handles  # noqa: E402


class Base(DeclarativeBase):
    """The tables these tests declare."""


class Onboarding(Base, Workflow):
    """A run keyed on the event that started it, with two other unique keys."""

    __tablename__ = "handles_onboarding"
    __table_args__ = (
        UniqueConstraint("team", "seat", name="uq_handles_onboarding_seat"),
        Index("ix_handles_onboarding_note", "note"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String, unique=True)
    trigger_key: Mapped[str | None] = mapped_column(String, unique=True, default=None)
    team: Mapped[str] = mapped_column(String, default=lambda: uuid.uuid4().hex)
    seat: Mapped[int] = mapped_column(default=0)
    note: Mapped[str] = mapped_column(String, default="")

    @step
    async def welcome(self):
        """Do nothing; only the start is under test."""
        return


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
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


@in_module_loop
async def test_a_repeat_of_the_key_returns_false(session_factory):
    key = uuid.uuid4().hex
    first = Onboarding(user_id=f"u-{key}", trigger_key=key)
    assert await first.start(Onboarding.welcome, key=Onboarding.trigger_key) is True
    assert first.id is not None

    # A resend: the same key, whatever else the row says.
    resend = Onboarding(user_id=f"other-{key}", trigger_key=key)
    assert await resend.start(Onboarding.welcome, key=Onboarding.trigger_key) is False
    assert resend.id is None


@in_module_loop
async def test_a_clash_on_another_unique_column_raises_run_conflict(session_factory):
    user = f"u-{uuid.uuid4().hex}"
    assert await Onboarding(user_id=user, trigger_key=uuid.uuid4().hex).start(
        Onboarding.welcome, key=Onboarding.trigger_key
    )

    with pytest.raises(RunConflict) as raised:
        await Onboarding(user_id=user, trigger_key=uuid.uuid4().hex).start(
            Onboarding.welcome, key=Onboarding.trigger_key
        )
    assert raised.value.constraint == "handles_onboarding_user_id_key"
    assert str(raised.value) == (
        "the row clashes with an existing one on handles_onboarding_user_id_key"
    )


@in_module_loop
async def test_a_clash_on_a_named_multi_column_constraint_is_named(session_factory):
    team = uuid.uuid4().hex
    assert await Onboarding(
        user_id=f"u-{uuid.uuid4().hex}", trigger_key=uuid.uuid4().hex, team=team
    ).start(Onboarding.welcome, key=Onboarding.trigger_key)

    with pytest.raises(RunConflict) as raised:
        await Onboarding(
            user_id=f"u-{uuid.uuid4().hex}", trigger_key=uuid.uuid4().hex, team=team
        ).start(Onboarding.welcome, key=Onboarding.trigger_key)
    assert raised.value.constraint == "uq_handles_onboarding_seat"


@in_module_loop
async def test_without_key_any_clash_returns_false(session_factory):
    user = f"u-{uuid.uuid4().hex}"
    assert await Onboarding(user_id=user).start(Onboarding.welcome) is True
    assert await Onboarding(user_id=user).start(Onboarding.welcome) is False


@in_module_loop
async def test_the_primary_key_is_a_key(session_factory):
    row = Onboarding(user_id=f"u-{uuid.uuid4().hex}")
    assert await row.start(Onboarding.welcome, key=Onboarding.id) is True
    again = Onboarding(id=row.id, user_id=f"u-{uuid.uuid4().hex}")
    assert await again.start(Onboarding.welcome, key=Onboarding.id) is False


def _refusal(key: object) -> str:
    with pytest.raises((TypeError, ValueError)) as raised:
        handles.key_column(Onboarding, key)
    return f"{type(raised.value).__name__}: {raised.value}"


def test_key_must_be_one_unique_column_of_the_row():
    class Other(Base, Workflow):
        __tablename__ = "handles_other"

        id: Mapped[int] = mapped_column(primary_key=True)
        trigger_key: Mapped[str | None] = mapped_column(String, unique=True)

        @step
        async def go(self):
            """Do nothing."""
            return

    not_unique = "which is not unique on its own; give it unique=True."
    assert _refusal(Onboarding.note) == (
        f"ValueError: key= names Onboarding.note, {not_unique}"
    )
    assert _refusal(Onboarding.team) == (
        f"ValueError: key= names Onboarding.team, {not_unique}"
    )
    assert _refusal("trigger_key") == (
        "TypeError: key= must be one column of Onboarding, not 'trigger_key'."
    )
    assert _refusal(Other.trigger_key) == (
        f"TypeError: key= must be one column of Onboarding, not {Other.trigger_key!r}."
    )
    assert handles.key_column(Onboarding, Onboarding.trigger_key) is (
        Onboarding.__table__.c.trigger_key
    )
