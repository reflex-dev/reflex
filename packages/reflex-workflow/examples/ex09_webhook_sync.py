"""09 · Webhook ingestion and cross-system synchronization.

One run per entity rather than one per event: a webhook is delivered into the
entity's run, which applies it, pushes it to each destination, and goes back to
waiting for the next one. Events carry the version they were written at, so an
event that arrives late is ignored rather than undoing a newer one, and an event
that arrives while the run is busy is held until it is waiting again.

Each destination is a step, so a destination that is down is the only one
retried; the ones already written stay written, and the warehouse's asynchronous
callback is just another wait.
"""

from __future__ import annotations

import datetime
from typing import Any

from reflex_workflow import Step, Wait, Workflow, step, wait_for
from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from examples.base import Base
from examples.services import world

# Where an entity is mirrored, in order. The warehouse answers later, by callback.
DESTINATIONS = ("search", "cache", "warehouse")

CALLBACK_DEADLINE = datetime.timedelta(hours=6)
IDLE_DEADLINE = datetime.timedelta(days=30)

RETRIES = 3
BACKOFF = datetime.timedelta(milliseconds=50)


class Entity(Base, Workflow):
    """One synchronized entity, for as long as events keep arriving about it."""

    __tablename__ = "example_entity"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[str] = mapped_column(String, unique=True)
    # The highest version applied; anything older is a late duplicate.
    version: Mapped[int] = mapped_column(Integer, default=0)
    fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    written: Mapped[dict[str, str] | None] = mapped_column(JSONB, default=None)
    ignored: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="new")

    @step(retries=RETRIES, backoff=BACKOFF)
    async def idle(self) -> Wait[Entity]:
        """Wait for the next event about this entity.

        Returns:
            The wait for an event.
        """
        self.status = "idle"
        return wait_for(Entity.apply, timeout=IDLE_DEADLINE, on_timeout=Entity.retire)

    @step(retries=RETRIES, backoff=BACKOFF)
    async def apply(self, fields: dict[str, Any], version: int):
        """Take an event, unless a newer one has already been applied.

        Args:
            fields: What the event says the entity looks like.
            version: The version the event was written at.

        Returns:
            The enrichment, or straight back to waiting when it is stale.
        """
        if version <= self.version:
            # A replay or an event that overtook a newer one on the way here.
            self.ignored += 1
            return Entity.idle
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
            self.status = "awaiting-callback"
            return wait_for(
                Entity.confirm,
                timeout=CALLBACK_DEADLINE,
                on_timeout=Entity.give_up_on_callback,
            )
        if following < len(DESTINATIONS):
            return Entity.push(DESTINATIONS[following])
        return Entity.idle

    @step(retries=RETRIES, backoff=BACKOFF)
    async def confirm(self, job: str) -> Step[Entity, []]:
        """Take the warehouse's callback.

        Args:
            job: The job the warehouse ran.

        Returns:
            The wait for the next event.
        """
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

    The first event starts the entity's run; the rest are delivered into it,
    including one that arrives while the run is busy with the last.

    Args:
        entity_id: Which entity the event is about.
        fields: What the event says.
        version: The version it was written at.

    Returns:
        1 when the event was accepted, 0 when it was a duplicate.
    """
    started = await Entity(entity_id=entity_id).start(Entity.apply(fields, version))
    if started:
        return 1
    return await Entity.by(Entity.entity_id == entity_id).deliver(
        Entity.apply(fields, version), key=f"{entity_id}:v{version}"
    )
