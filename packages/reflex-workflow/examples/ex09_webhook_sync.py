"""09 · Webhook ingestion and cross-system synchronization.

One run per entity rather than one per event. A webhook is written to the
entity's inbox and the run is woken; whenever the run is idle it applies the
newest event it has not applied yet, pushes it to each destination, and goes back
to waiting. Events carry the version they were written at, so a replay is one row
of the inbox, an event that arrives late is never the newest and is not applied,
and one that arrives while the run is busy -- mid-push, or waiting on the
warehouse -- is in the inbox when the run is next idle.

Each destination is a step, so a destination that is down is the only one
retried; the ones already written stay written. The warehouse's asynchronous
callback is just another wait, and it names the job it is about, so a callback
for a job an older version started cannot complete the current one.
"""

from __future__ import annotations

import datetime
from typing import Any

from reflex_workflow import Call, Step, Wait, Workflow, step, wait_for
from reflex_workflow.engine.runtime import current
from sqlalchemy import Integer, String, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Mapped, mapped_column

from examples.base import Base
from examples.services import world

# Where an entity is mirrored, in order. The warehouse answers later, by callback.
DESTINATIONS = ("search", "cache", "warehouse")

CALLBACK_DEADLINE = datetime.timedelta(hours=6)
IDLE_DEADLINE = datetime.timedelta(days=30)

RETRIES = 3
BACKOFF = datetime.timedelta(milliseconds=50)


class EntityEvent(Base):
    """One webhook, kept until the entity's run is ready for it.

    An ordinary table: the webhook handler writes it and the run reads it.
    """

    __tablename__ = "example_entity_event"
    __table_args__ = (UniqueConstraint("entity_id", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[str] = mapped_column(String, index=True)
    version: Mapped[int] = mapped_column(Integer)
    fields: Mapped[dict[str, Any]] = mapped_column(JSONB)


class Entity(Base, Workflow):
    """One synchronized entity, for as long as events keep arriving about it."""

    __tablename__ = "example_entity"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[str] = mapped_column(String, unique=True)
    # The highest version applied; nothing at or below it is applied again.
    version: Mapped[int] = mapped_column(Integer, default=0)
    fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    written: Mapped[dict[str, str] | None] = mapped_column(JSONB, default=None)
    status: Mapped[str] = mapped_column(String, default="new")

    @step(retries=RETRIES, backoff=BACKOFF)
    # Annotated because idle and the steps after it return one another.
    async def idle(self) -> Call[Entity] | Wait[Entity]:
        """Apply the newest event in the inbox, or wait to be told of one.

        Returns:
            The newest event's application, or the wait for the next event.
        """
        async with current().session_factory() as session:
            newest = (
                await session.execute(
                    select(EntityEvent.version, EntityEvent.fields)
                    .where(
                        EntityEvent.entity_id == self.entity_id,
                        EntityEvent.version > self.version,
                    )
                    .order_by(EntityEvent.version.desc())
                    .limit(1)
                )
            ).first()
        if newest is not None:
            return Entity.apply(newest.fields, newest.version)
        self.status = "idle"
        return wait_for(Entity.idle, timeout=IDLE_DEADLINE, on_timeout=Entity.retire)

    @step(retries=RETRIES, backoff=BACKOFF)
    async def apply(self, fields: dict[str, Any], version: int):
        """Take an event: the newest there is, which makes the older ones moot.

        Args:
            fields: What the event says the entity looks like.
            version: The version the event was written at.

        Returns:
            The enrichment.
        """
        self.fields, self.version = fields, version
        self.status = f"applying:{version}"
        return Entity.enrich

    @step(retries=RETRIES, backoff=BACKOFF)
    async def enrich(self):
        """Fill in what the event did not carry.

        Returns:
            The first destination.
        """
        extra = await world.call(
            "enrichment.lookup",
            key=f"{self.entity_id}:v{self.version}",
            entity=self.entity_id,
        )
        self.fields = {**(self.fields or {}), "enriched": extra["id"]}
        return Entity.push(DESTINATIONS[0])

    @step(retries=RETRIES, backoff=BACKOFF)
    async def push(self, destination: str):
        """Write the entity to one destination.

        Args:
            destination: Where to write it.

        Returns:
            The next destination, the wait for a callback, or back to idle.
        """
        written = await world.call(
            f"{destination}.write",
            key=f"{self.entity_id}:v{self.version}",
            entity=self.entity_id,
            fields=self.fields,
        )
        self.written = {**(self.written or {}), destination: written["id"]}
        self.status = f"written:{destination}"
        following = DESTINATIONS.index(destination) + 1
        if destination == "warehouse":
            # The warehouse takes the job and answers when it has run it.
            return self.awaiting_callback()
        if following < len(DESTINATIONS):
            return Entity.push(DESTINATIONS[following])
        return Entity.idle

    def awaiting_callback(self) -> Wait[Entity]:
        """Wait for the warehouse to say it has run this version's job.

        Returns:
            The wait for the callback.
        """
        self.status = "awaiting-callback"
        return wait_for(
            Entity.confirm,
            timeout=CALLBACK_DEADLINE,
            on_timeout=Entity.give_up_on_callback,
        )

    @step(retries=RETRIES, backoff=BACKOFF)
    async def confirm(self, job: str) -> Step[Entity, []] | Wait[Entity]:
        """Take the warehouse's callback, if it is about this version's job.

        Args:
            job: The job the warehouse ran.

        Returns:
            The wait for the next event, or the same wait again for a callback
            about a job an older version started.
        """
        if job != (self.written or {}).get("warehouse"):
            return self.awaiting_callback()
        self.written = {**(self.written or {}), "warehouse-job": job}
        self.status = "synchronized"
        return Entity.idle

    @step(retries=RETRIES, backoff=BACKOFF)
    async def give_up_on_callback(self) -> Step[Entity, []]:
        """Stop waiting for a warehouse that never answered.

        Returns:
            The wait for the next event.
        """
        self.status = "callback-timed-out"
        return Entity.idle

    @step(retries=RETRIES, backoff=BACKOFF)
    async def retire(self):
        """Close an entity nothing has said anything about for a month."""
        self.status = "retired"


async def receive(entity_id: str, fields: dict[str, Any], version: int) -> int:
    """Take a webhook about one entity.

    The event is kept before the run hears of it, so it is never lost to a run
    that was busy: a run that is waiting takes it now, and one that is not finds
    it the next time it is idle.

    Args:
        entity_id: Which entity the event is about.
        fields: What the event says.
        version: The version it was written at.

    Returns:
        1 when the event was taken, 0 when it was a replay of one already taken.
    """
    async with current().session_factory() as session, session.begin():
        added = (
            await session.execute(
                pg_insert(EntityEvent)
                .values(entity_id=entity_id, version=version, fields=fields)
                .on_conflict_do_nothing()
                .returning(EntityEvent.id)
            )
        ).first()
    if added is None:
        return 0
    if not await Entity(entity_id=entity_id).start(Entity.idle):
        await Entity.by(Entity.entity_id == entity_id).deliver(
            Entity.idle(), key=f"{entity_id}:v{version}"
        )
    return 1


async def callback(entity_id: str, job: str) -> int:
    """Take the warehouse's callback about a job it ran.

    Args:
        entity_id: The entity the job was for.
        job: The job.

    Returns:
        1 when the entity took the callback, 0 when it was not waiting for one or
        had already taken this one.
    """
    return await Entity.by(Entity.entity_id == entity_id).deliver(
        Entity.confirm(job), key=f"{entity_id}:{job}"
    )
