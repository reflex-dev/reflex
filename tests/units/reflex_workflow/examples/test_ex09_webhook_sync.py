"""09 · Webhook ingestion and cross-system synchronization.

Pass condition: duplicate and out-of-order events produce the correct final
state; callbacks survive restarts; one failing destination does not erase
successful writes.
"""

from __future__ import annotations

import uuid

import pytest
from examples.ex09_webhook_sync import DESTINATIONS, Entity, receive
from examples.services import world
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .conftest import eventually, worker

pytestmark = pytest.mark.asyncio(loop_scope="module")


def reaches(entity_id: str, status: str):
    """Build a check that an entity has reached a status.

    Args:
        entity_id: The entity.
        status: The status to wait for.

    Returns:
        An async predicate.
    """

    async def check() -> bool:
        row = await Entity.by(Entity.entity_id == entity_id).get()
        return row is not None and row.status == status

    return check


async def read_directly(
    factory: async_sessionmaker[AsyncSession], entity_id: str
) -> Entity:
    """Read an entity without going through the engine.

    Args:
        factory: The session factory for the test database.
        entity_id: The entity.

    Returns:
        The row.
    """
    async with factory() as session:
        row = (
            (await session.execute(select(Entity).where(Entity.entity_id == entity_id)))
            .scalars()
            .first()
        )
    assert row is not None
    return row


async def confirmed(entity_id: str, job: str = "job-1") -> None:
    """Answer the warehouse callback the entity is waiting for.

    Args:
        entity_id: The entity.
        job: The job the warehouse ran.
    """
    await eventually(reaches(entity_id, "awaiting-callback"))
    assert (
        await Entity.by(Entity.entity_id == entity_id).deliver(
            Entity.confirm(job), key=f"{entity_id}-{job}"
        )
        == 1
    )


def ignored(entity_id: str, count: int):
    """Build a check that the entity has dropped a number of events.

    Args:
        entity_id: The entity.
        count: How many events should have been ignored.

    Returns:
        An async predicate.
    """

    async def check() -> bool:
        row = await Entity.by(Entity.entity_id == entity_id).get()
        return row is not None and row.ignored == count

    return check


async def test_an_event_is_enriched_and_written_everywhere(running):
    entity = uuid.uuid4().hex
    assert await receive(entity, {"name": "first"}, version=1) == 1
    await confirmed(entity)
    await eventually(reaches(entity, "idle"))

    row = await Entity.by(Entity.entity_id == entity).get()
    assert row is not None
    assert set(row.written or {}) == {*DESTINATIONS, "warehouse-job"}
    assert (row.version, row.ignored) == (1, 0)
    assert (row.fields or {})["enriched"] is not None


async def test_a_replayed_event_changes_nothing(running):
    entity = uuid.uuid4().hex
    assert await receive(entity, {"name": "first"}, version=1) == 1
    await confirmed(entity)
    await eventually(reaches(entity, "idle"))

    # The provider redelivers the same event. The run's key history only covers
    # events that were delivered into it, and the first one started it instead,
    # so this replay is taken in and then dropped by the version it carries.
    assert await receive(entity, {"name": "first"}, version=1) == 1
    await eventually(ignored(entity, 1))

    row = await Entity.by(Entity.entity_id == entity).get()
    assert row is not None
    assert (row.version, row.status) == (1, "idle")
    # Nothing was rewritten anywhere: the replay cost one step and no writes.
    assert world.attempts("search.write") == 1
    assert world.attempts("enrichment.lookup") == 1

    # A replay of an event that was delivered rather than started is refused
    # outright, without a step running at all.
    assert await receive(entity, {"name": "second"}, version=2) == 1
    await confirmed(entity, "job-v2")
    await eventually(reaches(entity, "idle"))
    assert await receive(entity, {"name": "second"}, version=2) == 0


async def test_an_event_that_arrives_late_does_not_undo_a_newer_one(running):
    entity = uuid.uuid4().hex
    assert await receive(entity, {"name": "first"}, version=1) == 1
    await confirmed(entity, "job-v1")
    await eventually(reaches(entity, "idle"))

    assert await receive(entity, {"name": "third"}, version=3) == 1
    await confirmed(entity, "job-v3")
    await eventually(reaches(entity, "idle"))

    # Version 2 turns up after version 3: it must be dropped, not applied.
    assert await receive(entity, {"name": "second"}, version=2) == 1
    await eventually(ignored(entity, 1))

    row = await Entity.by(Entity.entity_id == entity).get()
    assert row is not None
    assert (row.fields or {})["name"] == "third"
    assert (row.version, row.ignored, row.status) == (3, 1, "idle")


async def test_a_failing_destination_does_not_erase_the_successful_ones(running):
    entity = uuid.uuid4().hex
    world.break_next("cache.write", times=2)
    assert await receive(entity, {"name": "first"}, version=1) == 1
    await confirmed(entity)
    await eventually(reaches(entity, "idle"))

    row = await Entity.by(Entity.entity_id == entity).get()
    assert row is not None
    # The cache was retried; search was written once and kept its id.
    assert world.attempts("cache.write") == 3
    assert world.attempts("search.write") == 1
    assert set(row.written or {}) == {*DESTINATIONS, "warehouse-job"}


async def test_a_callback_outlives_the_worker_that_asked_for_it(database):
    entity = uuid.uuid4().hex
    async with worker(database):
        assert await receive(entity, {"name": "first"}, version=1) == 1
        await eventually(reaches(entity, "awaiting-callback"))

    parked = await read_directly(database, entity)
    assert (parked.status, parked.waiting_for) == ("awaiting-callback", "confirm")

    async with worker(database):
        assert (
            await Entity.by(Entity.entity_id == entity).deliver(
                Entity.confirm("job-after-restart"), key=f"{entity}-late"
            )
            == 1
        )
        await eventually(reaches(entity, "idle"))

    row = await read_directly(database, entity)
    assert (row.written or {})["warehouse-job"] == "job-after-restart"
    assert world.attempts("warehouse.write") == 1
