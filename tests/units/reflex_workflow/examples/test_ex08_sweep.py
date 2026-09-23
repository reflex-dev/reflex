"""08 · Scheduled collection and deadline processing.

Pass condition: restart or overlap schedulers without duplicating an occurrence;
moving a deadline prevents early execution; burst coalescing preserves distinct
work.
"""

from __future__ import annotations

import datetime
import uuid

import pytest
from examples import ex08_sweep
from examples.ex08_sweep import BATCH, Collection, Sweep, Watch, schedule_sweep
from examples.services import world
from reflex_workflow import connect_workflows
from sqlalchemy import insert, select, update

from .conftest import eventually, worker

pytestmark = pytest.mark.asyncio(loop_scope="module")

MINUTE = datetime.timedelta(minutes=1)


def now() -> datetime.datetime:
    """Return the current moment.

    Returns:
        Now, in UTC.
    """
    return datetime.datetime.now(datetime.timezone.utc)


async def watch(database, item: str, due_in: datetime.timedelta, signals: int = 0):
    """Add something to watch.

    Args:
        database: The session factory for the test database.
        item: What to watch.
        due_in: How far from now its deadline is.
        signals: How many signals have already arrived for it.
    """
    async with database() as session, session.begin():
        await session.execute(
            insert(Watch).values(
                item=item, due_at=now() + due_in, every_seconds=3600, signals=signals
            )
        )


async def move_deadline(database, item: str, due_in: datetime.timedelta) -> None:
    """Move a watch's deadline.

    Args:
        database: The session factory for the test database.
        item: Which watch to move.
        due_in: How far from now the new deadline is.
    """
    async with database() as session, session.begin():
        await session.execute(
            update(Watch).where(Watch.item == item).values(due_at=now() + due_in)
        )


async def sweep_once(database, name: str) -> Sweep:
    """Run one pass of a sweeper and wait for it to finish.

    Args:
        database: The session factory for the test database.
        name: Which sweeper to run.

    Returns:
        The sweeper's row after the pass.
    """
    assert await schedule_sweep(name)

    async def swept() -> bool:
        row = await Sweep.by(Sweep.name == name).get()
        return row is not None and row.passes >= 1

    await eventually(swept)
    row = await Sweep.by(Sweep.name == name).get()
    assert row is not None
    return row


async def collections_for(database, item: str) -> list[Collection]:
    """List the collections started for one item.

    Args:
        database: The session factory for the test database.
        item: The item.

    Returns:
        Its collections.
    """
    async with database() as session:
        return list(
            (await session.execute(select(Collection).where(Collection.item == item)))
            .scalars()
            .all()
        )


async def test_a_pass_collects_what_is_due_and_leaves_what_is_not(database):
    due, later = f"due-{uuid.uuid4().hex}", f"later-{uuid.uuid4().hex}"
    await watch(database, due, -MINUTE)
    await watch(database, later, MINUTE * 30)

    async with worker(database):
        await sweep_once(database, f"sweeper-{uuid.uuid4().hex}")
        await eventually(lambda: world.attempts("collector.gather") >= 1)

    assert len(await collections_for(database, due)) == 1
    assert await collections_for(database, later) == []


async def test_moving_a_deadline_forward_holds_the_work_back(database):
    item = f"moved-{uuid.uuid4().hex}"
    await watch(database, item, -MINUTE)
    # The deadline moves before the sweep looks, so this pass must not see it.
    await move_deadline(database, item, MINUTE * 30)

    async with worker(database):
        swept = await sweep_once(database, f"sweeper-{uuid.uuid4().hex}")

    assert await collections_for(database, item) == []
    assert swept.started == 0


async def test_two_sweepers_at_once_start_one_collection_per_occurrence(database):
    items = [f"shared-{uuid.uuid4().hex}" for _ in range(5)]
    for item in items:
        await watch(database, item, -MINUTE)
    names = [f"sweeper-{side}-{uuid.uuid4().hex}" for side in "ab"]

    # Both sweepers are due before any worker runs, so one claim takes both and
    # their passes run side by side over the same due watches.
    async with connect_workflows(database):
        for name in names:
            assert await schedule_sweep(name)

    async with worker(database):

        async def both_swept() -> bool:
            rows = await Sweep.by(Sweep.name.in_(names)).all()
            return len(rows) == 2 and all(row.passes >= 1 for row in rows)

        await eventually(both_swept)
        await eventually(lambda: world.attempts("collector.gather") >= len(items))
        sweepers = await Sweep.by(Sweep.name.in_(names)).all()

    for item in items:
        assert len(await collections_for(database, item)) == 1
    # Between them they started every occurrence, and neither started one twice.
    assert sum(row.started for row in sweepers) == len(items)
    assert len(world.effects("collector.gather")) == len(items)


async def test_a_burst_of_signals_becomes_one_collection_that_counts_them(database):
    noisy, quiet = f"noisy-{uuid.uuid4().hex}", f"quiet-{uuid.uuid4().hex}"
    await watch(database, noisy, -MINUTE, signals=50)
    await watch(database, quiet, -MINUTE, signals=1)

    async with worker(database):
        await sweep_once(database, f"sweeper-{uuid.uuid4().hex}")
        await eventually(lambda: world.attempts("collector.gather") >= 2)

    [collected] = await collections_for(database, noisy)
    # One collection, and the fifty signals that caused it are not lost.
    assert collected.signals == 50
    assert len(await collections_for(database, quiet)) == 1


async def test_a_pass_takes_no_more_than_its_batch(database):
    items = [f"many-{uuid.uuid4().hex}" for _ in range(BATCH + 3)]
    for item in items:
        await watch(database, item, -MINUTE)

    async with worker(database):
        swept = await sweep_once(database, f"sweeper-{uuid.uuid4().hex}")

    assert swept.started == BATCH
    started = 0
    for item in items:
        started += len(await collections_for(database, item))
    assert started == BATCH


async def test_a_collection_that_fails_to_start_is_not_lost(database, monkeypatch):
    item = f"flaky-{uuid.uuid4().hex}"
    await watch(database, item, -MINUTE)
    real_start = ex08_sweep.start_collection
    blips = [RuntimeError("the database blinked")]

    async def start_or_blip(due: dict[str, object]) -> bool:
        if due["item"] == item and blips:
            raise blips.pop()
        return await real_start(due)

    monkeypatch.setattr(ex08_sweep, "start_collection", start_or_blip)
    async with worker(database):
        await sweep_once(database, f"sweeper-{uuid.uuid4().hex}")
        # The failed pass moved no deadline, so its retry starts the collection.
        await eventually(lambda: world.attempts("collector.gather") >= 1)

    assert len(await collections_for(database, item)) == 1
