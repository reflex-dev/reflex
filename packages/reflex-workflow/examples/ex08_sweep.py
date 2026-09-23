"""08 · Scheduled collection and deadline processing.

A sweep runs on a schedule, finds the watches whose deadline has passed, and
starts one collection for each. The collection's key is the watch and the
deadline it was due at, so two sweepers running at once — or one restarting
mid-pass — still produce one collection per occurrence.

Signals that arrive between passes coalesce: a watch that was poked fifty times
is collected once, and the count of what arrived is carried into the collection
rather than lost. Moving a deadline forward is all it takes to hold a watch back;
the next pass simply does not see it.
"""

from __future__ import annotations

import datetime
from typing import Any

from reflex_workflow import Every, Workflow, every, step
from reflex_workflow.engine.runtime import current
from sqlalchemy import DateTime, Integer, String, select, update
from sqlalchemy.orm import Mapped, mapped_column

from examples.base import Base
from examples.services import world

# How often the sweep looks, and how many watches one pass may take on. The cap
# is what keeps a backlog from becoming one enormous pass.
SWEEP_INTERVAL = datetime.timedelta(minutes=5)
BATCH = 10

RETRIES = 3
BACKOFF = datetime.timedelta(milliseconds=50)


class Watch(Base):
    """Something being watched, and when it is next due.

    An ordinary table: the sweep reads and writes it, and it holds no workflow
    state of its own.
    """

    __tablename__ = "example_watch"

    id: Mapped[int] = mapped_column(primary_key=True)
    item: Mapped[str] = mapped_column(String, unique=True)
    due_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    every_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    # Bumped by whatever pokes the watch between passes; a burst is one pass.
    signals: Mapped[int] = mapped_column(Integer, default=0)


class Collection(Base, Workflow):
    """One collection of one watch, for one deadline."""

    __tablename__ = "example_collection"

    id: Mapped[int] = mapped_column(primary_key=True)
    # "this item, for this deadline": what makes an occurrence one run.
    occurrence: Mapped[str] = mapped_column(String, unique=True)
    item: Mapped[str] = mapped_column(String)
    signals: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str | None] = mapped_column(String, default=None)
    status: Mapped[str] = mapped_column(String, default="queued")

    @step(retries=RETRIES, backoff=BACKOFF)
    async def collect(self):
        """Gather the item, once per occurrence."""
        gathered = await world.call(
            "collector.gather",
            key=self.occurrence,
            item=self.item,
            signals=self.signals,
        )
        self.result = gathered["id"]
        self.status = "collected"


class Sweep(Base, Workflow):
    """A recurring pass over the watches that are due."""

    __tablename__ = "example_sweep"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    passes: Mapped[int] = mapped_column(Integer, default=0)
    started: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="new")

    @step(retries=RETRIES, backoff=BACKOFF)
    # Annotated because the step returns its own schedule: its type would
    # otherwise be defined in terms of itself.
    async def run_pass(self) -> Every[Sweep]:
        """Start a collection for every watch whose deadline has passed.

        The deadline moves forward and the signals reset in the same statement
        that hands the watch to this pass, so a second sweeper looking at the
        same moment sees the watch already moved on.

        Returns:
            This step again, on the sweep's schedule.
        """
        factory = current().session_factory
        async with factory() as session, session.begin():
            due = (
                await session.execute(
                    select(Watch)
                    .where(Watch.due_at <= datetime.datetime.now(datetime.timezone.utc))
                    .order_by(Watch.due_at)
                    .limit(BATCH)
                    .with_for_update(skip_locked=True)
                )
            ).scalars()
            taken = [
                {
                    "item": watch.item,
                    "due_at": watch.due_at,
                    "signals": watch.signals,
                    "every_seconds": watch.every_seconds,
                }
                for watch in due
            ]
            for watch in taken:
                await session.execute(
                    update(Watch)
                    .where(Watch.item == watch["item"])
                    .values(
                        due_at=watch["due_at"]
                        + datetime.timedelta(seconds=watch["every_seconds"]),
                        signals=0,
                    )
                )

        self.passes += 1
        self.started += sum([await start_collection(watch) for watch in taken])
        self.status = "swept"
        return every(Sweep.run_pass, SWEEP_INTERVAL)


async def start_collection(watch: dict[str, Any]) -> bool:
    """Start the collection for one watch and deadline.

    Args:
        watch: The watch's item, deadline, and signal count.

    Returns:
        Whether this call started it, rather than another sweeper.
    """
    occurrence = f"{watch['item']}@{watch['due_at'].isoformat()}"
    return await Collection(
        occurrence=occurrence, item=watch["item"], signals=watch["signals"]
    ).start(Collection.collect)


async def schedule_sweep(name: str) -> bool:
    """Declare a sweeper, without duplicating it on restart.

    Args:
        name: Which sweeper this is.

    Returns:
        Whether this call created it.
    """
    return await Sweep(name=name).start(Sweep.run_pass)
