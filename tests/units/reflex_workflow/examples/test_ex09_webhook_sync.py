"""09 · Webhook ingestion and cross-system synchronization.

Pass condition: duplicate and out-of-order events produce the correct final
state; callbacks survive restarts; one failing destination does not erase
successful writes.
"""

from __future__ import annotations

import asyncio
import datetime
import time
import uuid

import pytest
from examples import ex09_webhook_sync
from examples.ex09_webhook_sync import DESTINATIONS, Entity, callback, receive
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
        """Tell whether the entity has reached the status.

        Returns:
            Whether it has.
        """
        row = await Entity.by(Entity.entity_id == entity_id).get()
        return row is not None and row.status == status

    return check


def at_version(entity_id: str, version: int, status: str):
    """Build a check that an entity has applied a version and reached a status.

    Args:
        entity_id: The entity.
        version: The version it should have applied.
        status: The status to wait for.

    Returns:
        An async predicate.
    """

    async def check() -> bool:
        """Tell whether the entity has applied the version and reached the status.

        Returns:
            Whether it has.
        """
        row = await Entity.by(Entity.entity_id == entity_id).get()
        return row is not None and (row.version, row.status) == (version, status)

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


async def warehouse_job(entity_id: str) -> str:
    """Return the warehouse job the entity is waiting to hear about.

    Args:
        entity_id: The entity.

    Returns:
        The job's id.
    """
    row = await Entity.by(Entity.entity_id == entity_id).get()
    assert row is not None
    return (row.written or {})["warehouse"]


async def confirmed(entity_id: str) -> str:
    """Answer the warehouse callback the entity is waiting for.

    Args:
        entity_id: The entity.

    Returns:
        The job the callback was about.
    """
    await eventually(reaches(entity_id, "awaiting-callback"))
    job = await warehouse_job(entity_id)
    assert await callback(entity_id, job) == 1
    return job


async def test_an_event_is_enriched_and_written_everywhere(running):
    entity = uuid.uuid4().hex
    assert await receive(entity, {"name": "first"}, version=1) == 1
    await confirmed(entity)
    await eventually(reaches(entity, "idle"))

    row = await Entity.by(Entity.entity_id == entity).get()
    assert row is not None
    assert set(row.written or {}) == {*DESTINATIONS, "warehouse-job"}
    assert row.version == 1
    assert (row.fields or {})["enriched"] is not None


async def test_a_replayed_event_changes_nothing(running):
    entity = uuid.uuid4().hex
    assert await receive(entity, {"name": "first"}, version=1) == 1
    await confirmed(entity)
    await eventually(reaches(entity, "idle"))

    # The provider redelivers the event: it is the same row of the inbox.
    assert await receive(entity, {"name": "first"}, version=1) == 0
    assert await receive(entity, {"name": "second"}, version=2) == 1
    await confirmed(entity)
    await eventually(at_version(entity, 2, "idle"))
    assert await receive(entity, {"name": "second"}, version=2) == 0

    # Each version was written once, however often it was delivered.
    assert world.attempts("search.write") == 2
    assert world.attempts("enrichment.lookup") == 2


async def test_an_event_that_arrives_late_does_not_undo_a_newer_one(running):
    entity = uuid.uuid4().hex
    assert await receive(entity, {"name": "first"}, version=1) == 1
    await confirmed(entity)
    await eventually(at_version(entity, 1, "idle"))

    assert await receive(entity, {"name": "third"}, version=3) == 1
    await confirmed(entity)
    await eventually(at_version(entity, 3, "idle"))

    # Version 2 turns up after version 3: it is kept, and never applied.
    assert await receive(entity, {"name": "second"}, version=2) == 1
    await eventually(at_version(entity, 3, "idle"))

    row = await Entity.by(Entity.entity_id == entity).get()
    assert row is not None
    assert (row.fields or {})["name"] == "third"
    assert world.attempts("enrichment.lookup") == 2


async def test_an_event_during_a_callback_wait_is_applied_after_it(running):
    entity = uuid.uuid4().hex
    assert await receive(entity, {"name": "first"}, version=1) == 1
    await eventually(reaches(entity, "awaiting-callback"))

    # Two more arrive while the run waits on the warehouse; neither is lost.
    assert await receive(entity, {"name": "second"}, version=2) == 1
    assert await receive(entity, {"name": "third"}, version=3) == 1
    await confirmed(entity)

    # The newest is what the run applies once it is idle again.
    await eventually(at_version(entity, 3, "awaiting-callback"))
    await confirmed(entity)
    await eventually(at_version(entity, 3, "idle"))
    row = await Entity.by(Entity.entity_id == entity).get()
    assert row is not None
    assert (row.fields or {})["name"] == "third"


async def test_a_callback_about_an_older_job_does_not_complete_the_wait(
    running, monkeypatch
):
    entity = uuid.uuid4().hex
    monkeypatch.setattr(
        ex09_webhook_sync, "CALLBACK_DEADLINE", datetime.timedelta(milliseconds=300)
    )
    assert await receive(entity, {"name": "first"}, version=1) == 1
    await eventually(reaches(entity, "awaiting-callback"))
    first_job = await warehouse_job(entity)
    # The warehouse is slow with version 1's job, and the run stops waiting.
    await eventually(reaches(entity, "idle"))

    monkeypatch.setattr(
        ex09_webhook_sync, "CALLBACK_DEADLINE", datetime.timedelta(hours=6)
    )
    assert await receive(entity, {"name": "second"}, version=2) == 1
    await eventually(at_version(entity, 2, "awaiting-callback"))

    # Version 1's job finally reports in while version 2's is outstanding.
    assert await callback(entity, first_job) == 1
    await eventually(at_version(entity, 2, "awaiting-callback"))
    row = await Entity.by(Entity.entity_id == entity).get()
    assert row is not None
    assert "warehouse-job" not in (row.written or {})

    second_job = await confirmed(entity)
    await eventually(at_version(entity, 2, "idle"))
    row = await Entity.by(Entity.entity_id == entity).get()
    assert row is not None
    assert (row.written or {})["warehouse-job"] == second_job != first_job


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
    job = (parked.written or {})["warehouse"]

    async with worker(database):
        assert await callback(entity, job) == 1
        await eventually(reaches(entity, "idle"))

    row = await read_directly(database, entity)
    assert (row.written or {})["warehouse-job"] == job
    assert world.attempts("warehouse.write") == 1


async def test_a_retired_entity_comes_back_for_a_new_event(running, monkeypatch):
    monkeypatch.setattr(
        ex09_webhook_sync, "IDLE_DEADLINE", datetime.timedelta(milliseconds=300)
    )
    entity = uuid.uuid4().hex
    assert await receive(entity, {"name": "first"}, version=1) == 1
    await confirmed(entity)
    await eventually(reaches(entity, "retired"))

    monkeypatch.setattr(ex09_webhook_sync, "IDLE_DEADLINE", datetime.timedelta(days=30))
    assert await receive(entity, {"name": "second"}, version=2) == 1
    await confirmed(entity)
    await eventually(at_version(entity, 2, "idle"))


async def test_callbacks_about_other_jobs_do_not_put_the_deadline_off(
    running, monkeypatch
):
    monkeypatch.setattr(
        ex09_webhook_sync, "CALLBACK_DEADLINE", datetime.timedelta(seconds=1)
    )
    entity = uuid.uuid4().hex
    assert await receive(entity, {"name": "first"}, version=1) == 1
    await eventually(reaches(entity, "awaiting-callback"))

    # Callbacks about jobs this version never started keep arriving, faster than
    # the deadline; the wait still gives up when its own deadline passes.
    started = time.monotonic()
    stale = 0
    while await reaches(entity, "awaiting-callback")():
        assert time.monotonic() - started < 5, "the deadline kept being put off"
        stale += 1
        await callback(entity, f"someone-elses-job-{stale}")
        await asyncio.sleep(0.2)
    assert stale > 1
