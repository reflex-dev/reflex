"""Tests for reflex_workflow.engine.claim, against a real Postgres.

Set REFLEX_TEST_POSTGRES to a postgresql:// URL for a database the tests may wipe.
"""

from __future__ import annotations

import asyncio
import collections
import datetime
import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import String, event, func, insert, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

URL = os.environ.get("REFLEX_TEST_POSTGRES", "")
ASYNC_URL = URL.replace("postgresql://", "postgresql+psycopg://", 1)

pytestmark = [
    pytest.mark.skipif(
        not URL, reason="set REFLEX_TEST_POSTGRES to test against Postgres"
    ),
    pytest.mark.asyncio(loop_scope="module"),
]

from reflex_workflow import Limit, Workflow, step  # noqa: E402
from reflex_workflow.engine.claim import claim  # noqa: E402
from reflex_workflow.engine.runtime import Runtime  # noqa: E402

ROWS = 200


class Base(DeclarativeBase):
    """Declarative base for the claim tests' tables."""


class Queued(Base, Workflow):
    """A workflow claimed a batch at a time."""

    __tablename__ = "wf_claim_queued"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer: Mapped[str] = mapped_column(String, index=True)

    @step
    async def work(self):
        """Never run: these tests claim rows and stop there."""


class Capped(Base, Workflow):
    """A workflow claimed a group at a time, no more than two of a group at once."""

    __tablename__ = "wf_claim_capped"
    __workflow_limit__ = Limit(by="customer", at_most=2)

    id: Mapped[int] = mapped_column(primary_key=True)
    customer: Mapped[str] = mapped_column(String, index=True)

    @step
    async def work(self):
        """Never run: these tests claim rows and stop there."""


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def runtime() -> AsyncIterator[Runtime]:
    """Fresh tables, and a runtime whose planner cannot hash or merge a join.

    Yields:
        A runtime to claim with.
    """
    engine = create_async_engine(ASYNC_URL)

    @event.listens_for(engine.sync_engine, "connect")
    def nested_loops_only(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("SET enable_hashjoin = off")
        cursor.execute("SET enable_mergejoin = off")
        cursor.close()
        dbapi_connection.commit()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        # The tests keep statistics stale on purpose; autovacuum would fix them.
        for table in Base.metadata.sorted_tables:
            await conn.exec_driver_sql(
                f"ALTER TABLE {table.name} SET (autovacuum_enabled = false)"
            )
    yield Runtime(
        async_sessionmaker(engine, expire_on_commit=False),
        asyncio.Event(),
        datetime.timedelta(seconds=30),
    )
    await engine.dispose()


async def due_behind_the_planners_back(
    runtime: Runtime, cls: type[Queued | Capped], customers: int
) -> None:
    """Fill a table with due rows the planner believes are not due yet.

    The rows are analyzed while they are due in an hour and then made due now, so
    the statistics say almost nothing is due. That is the state a worker polling a
    freshly seeded table is in, and it makes the planner rescan the subquery that
    picks rows once per candidate row.

    Args:
        runtime: The runtime whose database to write.
        cls: The workflow class.
        customers: How many customers to spread the rows over.
    """
    later = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    async with runtime.session_factory() as session, session.begin():
        await session.execute(
            insert(cls),
            [
                {
                    "customer": f"customer-{index % customers}",
                    "next_step": "work",
                    "wake_at": later,
                    "attempts": 0,
                    "wf_version": 0,
                }
                for index in range(ROWS)
            ],
        )
    async with runtime.session_factory() as session, session.begin():
        await (await session.connection()).exec_driver_sql(
            f"ANALYZE {cls.__tablename__}"
        )
        await session.execute(
            update(cls)
            .where(cls.next_step.is_not(None))
            .values(wake_at=func.now() - datetime.timedelta(seconds=1))
        )


async def test_a_claim_takes_no_more_than_its_limit(runtime):
    await due_behind_the_planners_back(runtime, Queued, customers=1)
    assert len(await claim(runtime, Queued, 8)) == 8


async def test_a_group_claim_takes_no_more_than_the_group_allows(runtime):
    await due_behind_the_planners_back(runtime, Capped, customers=4)
    claimed = await claim(runtime, Capped, 8)
    async with runtime.session_factory() as session:
        taken = dict(
            (
                await session.execute(
                    select(Capped.id, Capped.customer).where(
                        Capped.claimed_until.is_not(None)
                    )
                )
            )
            .tuples()
            .all()
        )
    assert sorted(pk for (pk,), _ in claimed) == sorted(taken)
    assert collections.Counter(taken.values()) == {
        f"customer-{index}": 2 for index in range(4)
    }
