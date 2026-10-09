"""Tests for reflex_workflow.engine.runner, end to end against a real Postgres.

Set REFLEX_TEST_POSTGRES to a postgresql:// URL for a database the tests may wipe.
"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import datetime
import inspect
import json
import os
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

import psycopg
import pytest
import pytest_asyncio
from sqlalchemy import DateTime, String, func, insert, literal, select, update
from sqlalchemy import event as sa_event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

URL = os.environ.get("REFLEX_TEST_POSTGRES", "")
ASYNC_URL = URL.replace("postgresql://", "postgresql+psycopg://", 1)

pytestmark = [
    pytest.mark.skipif(
        not URL, reason="set REFLEX_TEST_POSTGRES to test against Postgres"
    ),
    pytest.mark.asyncio(loop_scope="module"),
]

from reflex_workflow import (  # noqa: E402
    AttemptLog,
    Cron,
    Limit,
    RateBucket,
    Workflow,
    child,
    every,
    fan_out,
    model,
    run_workflows,
    step,
    wait_for,
    wake_in,
)
from reflex_workflow.engine import (  # noqa: E402
    claim,
    execute,
    notify,
    rows,
    runner,
    runtime,
)
from reflex_workflow.model import REGISTRY  # noqa: E402

LEASE = datetime.timedelta(seconds=2)
MINUTE = datetime.timedelta(minutes=1)

EVENTS: list[str] = []


class Base(DeclarativeBase):
    """Declarative base for the test tables."""


class Chain(Base, Workflow):
    """Two steps run back to back."""

    __tablename__ = "wf_test_chain"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def first(self):
        """Record and continue to the second step.

        Returns:
            The second step.
        """
        EVENTS.append(f"first:{self.key}")
        self.status = "first"
        return Chain.second

    @step
    async def second(self):
        """Record and stop."""
        EVENTS.append(f"second:{self.key}")
        self.status = "done"


class Delayed(Base, Workflow):
    """A step that waits before the next one."""

    __tablename__ = "wf_test_delayed"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def begin(self):
        """Wait a second before finishing.

        Returns:
            A one-second wait before ``finish``.
        """
        self.status = "waiting"
        return wake_in(Delayed.finish, datetime.timedelta(seconds=1))

    @step
    async def finish(self):
        """Record when the wait ended."""
        EVENTS.append(f"finish:{self.key}:{time.monotonic()}")
        self.status = "done"


class Flaky(Base, Workflow):
    """A step that fails twice, then succeeds."""

    __tablename__ = "wf_test_flaky"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step(retries=2, backoff=datetime.timedelta(milliseconds=200))
    async def call(self):
        """Fail twice with a transient error, then succeed."""
        EVENTS.append(f"attempt:{self.key}")
        if EVENTS.count(f"attempt:{self.key}") < 3:
            msg = "provider timed out"
            raise ConnectionError(msg)
        self.status = "done"


class Doomed(Base, Workflow):
    """A step that always fails."""

    __tablename__ = "wf_test_doomed"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step(retries=1, backoff=datetime.timedelta(milliseconds=200))
    async def call(self):
        """Change the row, then fail."""
        self.status = "half-done"
        msg = "card declined"
        raise ValueError(msg)


class Approval(Base, Workflow):
    """A run that waits for a decision from outside."""

    __tablename__ = "wf_test_approval"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def submit(self):
        """Wait for a decision."""
        self.status = "waiting"

    @step
    async def decide(self, decision: str, *, by: str = "manager"):
        """Apply a decision passed in from outside.

        Args:
            decision: The decision.
            by: Who decided.
        """
        self.status = f"decided:{decision}:{by}"


class Slow(Base, Workflow):
    """A slow step that can be preempted."""

    __tablename__ = "wf_test_slow"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def crawl(self):
        """Take two seconds, then set a status."""
        EVENTS.append(f"crawl-start:{self.key}")
        await asyncio.sleep(2)
        EVENTS.append(f"crawl-end:{self.key}")
        self.status = "crawled"

    @step
    async def override(self):
        """Set a different status."""
        self.status = "overridden"


class Long(Base, Workflow):
    """A step that outlasts its lease."""

    __tablename__ = "wf_test_long"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def work(self):
        """Take longer than the lease, so it only finishes once if renewed."""
        EVENTS.append(f"long-start:{self.key}")
        await asyncio.sleep(LEASE.total_seconds() * 1.5)
        self.status = "done"


class Racer(Base, Workflow):
    """A short step that many workers compete for."""

    __tablename__ = "wf_test_racer"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def go(self):
        """Record the run."""
        EVENTS.append(f"race:{self.key}")
        await asyncio.sleep(0.05)
        self.status = "done"


class ReviewSteps(Workflow):
    """A review that waits for a decision, with a deadline.

    Unmapped, so two tables can share it: one the fixture's worker runs, one a
    test drives by hand.
    """

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def submit(
        self,
        timeout_s: float = 60,
        pause_s: float = 0,
        expire_pause_s: float = 0,
        arm: bool = True,
    ):
        """Arm a wait for a decision.

        Args:
            timeout_s: Seconds before the review expires.
            pause_s: Seconds to stall before arming the wait.
            expire_pause_s: Seconds the expiry itself takes.
            arm: Whether to wait at all, rather than stopping.

        Returns:
            The wait for a decision, or None when the run just stops.
        """
        await asyncio.sleep(pause_s)
        if not arm:
            self.status = "withdrawn"
            return None
        self.status = "waiting"
        return wait_for(
            ReviewSteps.decide,
            timeout=datetime.timedelta(seconds=timeout_s),
            on_timeout=ReviewSteps.expire(pause_s=expire_pause_s),
        )

    @step
    async def decide(self, decision: str, *, by: str = "manager"):
        """Record a delivered decision, or wait for another one.

        Args:
            decision: The decision, or "again" to wait for one more.
            by: Who decided.

        Returns:
            Another wait when the decision was deferred.
        """
        EVENTS.append(f"decide:{self.key}")
        if decision == "again":
            self.status = "waiting"
            return wait_for(ReviewSteps.decide)
        self.status = f"decided:{decision}:{by}"
        return None

    @step
    async def expire(self, pause_s: float = 0):
        """Give up on the review.

        Args:
            pause_s: Seconds to take before giving up.
        """
        EVENTS.append(f"expire-start:{self.key}")
        await asyncio.sleep(pause_s)
        EVENTS.append(f"expire:{self.key}")
        self.status = "expired"


class Review(Base, ReviewSteps):
    """The review table the fixture's worker runs."""

    __tablename__ = "wf_test_review"


class RaceReview(Base, ReviewSteps):
    """A review table no worker runs, so a test can drive it step by step."""

    __tablename__ = "wf_test_race_review"


class Ticker(Base, Workflow):
    """A step that repeats on a fixed interval until it has run enough."""

    __tablename__ = "wf_test_ticker"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")
    ticks: Mapped[int] = mapped_column(default=0)

    @step
    async def tick(self):
        """Count one tick, and ask for another unless three have run.

        Returns:
            The schedule for the next tick, or None once done.
        """
        EVENTS.append(f"tick:{self.key}")
        self.ticks += 1
        if self.ticks >= 3:
            self.status = "done"
            return None
        return every(Ticker.tick, datetime.timedelta(seconds=1))


def unschedulable(now: datetime.datetime) -> datetime.datetime:
    """Stand in for a schedule that cannot say when to run next.

    Args:
        now: The current time.

    Raises:
        RuntimeError: Always.
    """
    msg = "no idea when"
    raise RuntimeError(msg)


class Noted(Base, Workflow):
    """A workflow whose own column has a default a caller may want to override."""

    __tablename__ = "wf_test_noted"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    note: Mapped[str | None] = mapped_column(String, default="pending")

    @step
    async def go(self):
        """Never run: this table is started and read, not worked."""


class Repeating(Base, Workflow):
    """Schedules a test drives by hand, so no wall-clock waiting is needed."""

    __tablename__ = "wf_test_repeating"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")
    ticks: Mapped[int] = mapped_column(default=0)

    @step
    async def tick(self, mode: str):
        """Count one tick and repeat on the schedule the mode names.

        Args:
            mode: Which schedule to repeat on.

        Returns:
            The schedule for the next tick.
        """
        self.ticks += 1
        if mode == "cron":
            return every(Repeating.tick("cron"), Cron("0 * * * *"))
        if mode == "broken":
            return every(Repeating.tick("broken"), unschedulable)
        return every(Repeating.tick("interval"), datetime.timedelta(minutes=1))


# How many items are running right now, and the most that ever ran together.
ITEMS = {"live": 0, "peak": 0}


class Item(Base, Workflow):
    """A child run, one per piece of fanned-out work."""

    __tablename__ = "wf_test_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def work(self, fail: bool = False):
        """Do the item's work, or fail at it.

        Args:
            fail: Whether to raise instead of finishing.

        Raises:
            RuntimeError: When asked to fail.
        """
        EVENTS.append(f"item:{self.key}")
        ITEMS["live"] += 1
        ITEMS["peak"] = max(ITEMS["peak"], ITEMS["live"])
        try:
            await asyncio.sleep(0.05)
            if fail:
                msg = "item gave up"
                raise RuntimeError(msg)
            self.status = "done"
        finally:
            ITEMS["live"] -= 1


class Batch(Base, Workflow):
    """A run that fans out to items and reports once they are all done."""

    __tablename__ = "wf_test_batch"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    size: Mapped[int] = mapped_column(default=3)
    failures: Mapped[int] = mapped_column(default=0)
    done: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def split(self, pause_s: float = 0):
        """Start one run per item.

        Args:
            pause_s: Seconds to stall before handing the children over.

        Returns:
            The fan-out, and the report to run after it.
        """
        EVENTS.append(f"split:{self.key}")
        await asyncio.sleep(pause_s)
        self.status = "running"
        return fan_out(
            (
                child(
                    Item(key=f"{self.key}-{index}"),
                    Item.work(fail=index < self.failures),
                )
                for index in range(self.size)
            ),
            then=Batch.report,
        )

    @step
    async def report(self):
        """Count what the children did."""
        items = await self.children(Item).all()
        self.done = sum(item.status == "done" for item in items)
        self.status = "reported"


# What each limited workflow is running right now, and the most it ever ran.
LIVE: dict[str, int] = collections.defaultdict(int)
PEAK: dict[str, int] = collections.defaultdict(int)


class Tenant(Base, Workflow):
    """A workflow that may only run so much of one customer's work at once."""

    __tablename__ = "wf_test_tenant"
    __workflow_limit__ = Limit(by="customer", at_most=2)

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    customer: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def work(self):
        """Hold a slot for a moment, recording how many the customer holds."""
        LIVE[self.customer] += 1
        PEAK[self.customer] = max(PEAK[self.customer], LIVE[self.customer])
        try:
            await asyncio.sleep(0.2)
            self.status = "done"
        finally:
            LIVE[self.customer] -= 1


class Quiet(Base, Workflow):
    """A workflow with one row, to see whether a busy table crowds it out."""

    __tablename__ = "wf_test_quiet"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def work(self):
        """Record when this row finally ran."""
        EVENTS.append(f"quiet:{self.key}")
        self.status = "done"


class Noisy(Base, Workflow):
    """A workflow with a large backlog of due rows."""

    __tablename__ = "wf_test_noisy"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def work(self):
        """Take a moment, so the backlog cannot clear instantly."""
        await asyncio.sleep(0.1)
        self.status = "done"


class Hog(Base, Workflow):
    """A backlog no shared worker touches, for the one-slot fairness test."""

    __tablename__ = "wf_test_hog"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def work(self):
        """Take a moment, so the backlog cannot clear instantly."""
        await asyncio.sleep(0.1)
        self.status = "done"


class Tiny(Base, Workflow):
    """One row behind the backlog, run by the same single-slot worker."""

    __tablename__ = "wf_test_tiny"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def work(self):
        """Record when this row finally ran."""
        EVENTS.append(f"tiny:{self.key}")
        self.status = "done"


class WorkflowRate(Base, RateBucket):
    """Where rate limits count, mapped onto the tests' own base."""

    __tablename__ = "wf_test_rate"


class Metered(Base, Workflow):
    """A workflow whose steps may only start so often, per provider."""

    __tablename__ = "wf_test_metered"
    __workflow_limit__ = Limit(by="provider", rate=4, per=datetime.timedelta(seconds=2))

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def work(self):
        """Record when this run got its turn."""
        STARTS[self.provider].append(time.monotonic())
        self.status = "done"


# When each provider's steps started, to see how often they were let through.
STARTS: dict[str, list[float]] = collections.defaultdict(list)


class Piece(Base, Workflow):
    """A child of Parked; no shared worker runs it, so a test can hold it still."""

    __tablename__ = "wf_test_piece"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def work(self):
        """Finish, which counts this piece off its parent."""
        self.status = "done"


class Parked(Base, Workflow):
    """A fan-out a test drives by hand, to watch the parent wait."""

    __tablename__ = "wf_test_parked"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    size: Mapped[int] = mapped_column(default=3)
    done: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def split(self):
        """Fan out to the pieces.

        Returns:
            The fan-out, and the report that follows it.
        """
        return fan_out(
            (
                child(Piece(key=f"{self.key}-{index}"), Piece.work)
                for index in range(self.size)
            ),
            then=Parked.report,
        )

    @step
    async def report(self):
        """Count the pieces that finished."""
        pieces = await self.children(Piece).all()
        self.done = sum(piece.status == "done" for piece in pieces)
        self.status = "reported"


class Rendered(Base, Workflow):
    """Work that only a worker with the right machine may run."""

    __tablename__ = "wf_test_rendered"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def prepare(self):
        """Do the ordinary part, anywhere.

        Returns:
            The rendering, which needs the other kind of worker.
        """
        EVENTS.append(f"prepare:{self.key}")
        self.status = "prepared"
        return Rendered.render

    @step(lane="gpu")
    async def render(self):
        """Do the part that needs a GPU.

        Returns:
            The wait for the file to be collected.
        """
        EVENTS.append(f"render:{self.key}")
        self.status = "rendered"
        return wait_for(Rendered.collect)

    @step(lane="gpu")
    async def collect(self):
        """Take the collected file, on the same kind of worker."""
        EVENTS.append(f"collect:{self.key}")
        self.status = "collected"


class WorkflowAttempt(Base, AttemptLog):
    """Where the tests' attempt history is written."""

    __tablename__ = "wf_test_attempt"


# One gate per execution of a Gated step, in start order, released by the test.
GATES = {1: asyncio.Event(), 2: asyncio.Event()}


class Gated(Base, Workflow):
    """A step that pauses until the test releases it; not run by the fixture's worker."""

    __tablename__ = "wf_test_gated"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def work(self):
        """Pause until this execution's gate opens, then record which one it was."""
        EVENTS.append(f"gated-start:{self.key}")
        execution = EVENTS.count(f"gated-start:{self.key}")
        await GATES[execution].wait()
        self.status = f"done:{execution}"


class Parting(Base, Workflow):
    """A step for a worker that is shut down mid-claim; not run by the fixture's."""

    __tablename__ = "wf_test_parting"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def work(self):
        """Record that the step ran."""
        self.status = "done"


class Budgeted(Base, Workflow):
    """A rate-limited workflow a test claims by hand; three starts an hour."""

    __tablename__ = "wf_test_budgeted"
    __workflow_limit__ = Limit(by="provider", rate=3, per=datetime.timedelta(hours=1))

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def work(self):
        """Finish."""
        self.status = "done"


class Deferring(Base, Workflow):
    """A workflow with a column SQLAlchemy loads only when it is read."""

    __tablename__ = "wf_test_deferring"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    notes: Mapped[str] = mapped_column(String, default="", deferred=True)

    @step
    async def work(self):
        """Add to the deferred column."""
        self.notes += "worked"


class Cramped(Base, Workflow):
    """A step whose body succeeds and whose commit cannot land."""

    __tablename__ = "wf_test_cramped"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    label: Mapped[str] = mapped_column(String(4), default="")

    @step(retries=1, backoff=datetime.timedelta(milliseconds=50))
    async def work(self):
        """Write more into a column than it can hold, having recorded the attempt."""
        EVENTS.append(f"cramped:{self.key}")
        self.label = "longer than the column"


class Leaf(Base, Workflow):
    """A child a test finishes by hand, to watch what its parent counts."""

    __tablename__ = "wf_test_leaf"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def work(self):
        """Finish, which is what the parent counts."""
        EVENTS.append(f"leaf:{self.key}")
        self.status = "done"


class Joined(Base, Workflow):
    """A parent whose children a test finishes one at a time."""

    __tablename__ = "wf_test_joined"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def split(self):
        """Fan out to three leaves.

        Returns:
            The fan-out, and the report to run once they are all done.
        """
        return fan_out(
            (child(Leaf(key=f"{self.key}-{index}"), Leaf.work) for index in range(3)),
            then=Joined.report,
        )

    @step
    async def report(self):
        """Record that every leaf is done."""
        EVENTS.append(f"joined-report:{self.key}")
        self.status = "reported"


# Held shut while a test needs its step to still be running at shutdown.
LINGERING = asyncio.Event()


class Lingering(Base, Workflow):
    """A step still running when its worker is told to stop; no worker runs it."""

    __tablename__ = "wf_test_lingering"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def work(self):
        """Stay in the step until the test lets go."""
        EVENTS.append(f"lingering:{self.key}")
        await LINGERING.wait()
        self.status = "done"


class Resting(Base, Workflow):
    """A run no worker takes, for asking when work is next due."""

    __tablename__ = "wf_test_resting"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)

    @step
    async def rest(self, hours: int = 0):
        """Sleep for a while, or stop.

        Args:
            hours: How long to wait before running again.

        Returns:
            The wait, when there is one.
        """
        return (
            wake_in(Resting.rest(), datetime.timedelta(hours=hours)) if hours else None
        )

    @step
    async def hop(self):
        """Go straight on to resting.

        Returns:
            The step to run now.
        """
        return Resting.rest()


class Crowded(Base, Workflow):
    """A workflow one customer may run only one of, to see what a pass considers."""

    __tablename__ = "wf_test_crowded"
    __workflow_limit__ = Limit(by="customer", at_most=1)

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    # Nullable, because the rows with no customer are a group of their own.
    customer: Mapped[str | None] = mapped_column(String, default=None)

    @step
    async def work(self):
        """Do nothing; this workflow is only ever claimed, never run."""


class Ticket(Base, Workflow):
    """A run keyed by columns json has no form of, and a number beside them."""

    __tablename__ = "wf_test_ticket"

    tenant: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    number: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def work(self):
        """Record and stop."""
        self.status = "done"


class Slot(Base, Workflow):
    """A child keyed by a moment, so the pointer back to its parent is one too."""

    __tablename__ = "wf_test_slot"

    at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def fill(self):
        """Record and stop, which releases the window."""
        self.status = "filled"


class Window(Base, Workflow):
    """A parent keyed by a moment, joining up with children keyed by one as well."""

    __tablename__ = "wf_test_window"

    at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    status: Mapped[str] = mapped_column(String, default="new")

    @step
    async def split(self):
        """Fan out to a slot a minute into the window, and another after it.

        Returns:
            The fan-out, gathering once both slots are filled.
        """
        return fan_out(
            [child(Slot(at=slot_at(self.at, n)), Slot.fill) for n in (1, 2)],
            then=Window.gather,
        )

    @step
    async def gather(self):
        """Record that every slot is filled."""
        self.status = "gathered"


def slot_at(start: datetime.datetime, minute: int) -> datetime.datetime:
    """Name the moment one of a window's slots is keyed by.

    Args:
        start: The window's own moment.
        minute: Which slot.

    Returns:
        The slot's key.
    """
    return start + datetime.timedelta(minutes=minute)


WORKFLOWS = [
    Chain,
    Delayed,
    Flaky,
    Doomed,
    Approval,
    Slow,
    Long,
    Racer,
    Review,
    Ticker,
    Batch,
    Item,
    Tenant,
    Quiet,
    Noisy,
    Metered,
    Ticket,
    Slot,
    Window,
    Cramped,
]


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Fresh tables and a running worker.

    Yields:
        A session factory for the test database.
    """
    engine = create_async_engine(ASYNC_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with run_workflows(
        factory,
        workflows=WORKFLOWS,
        poll_interval=datetime.timedelta(milliseconds=100),
        # A row written straight into the table announces nothing, so this is
        # how long the tests that write one wait to be noticed.
        max_idle_interval=datetime.timedelta(milliseconds=200),
        lease=LEASE,
    ):
        yield factory
    await engine.dispose()


async def wait_until(
    check: Callable[[], bool | Awaitable[bool]], timeout: float = 30
) -> None:
    """Poll until a check passes.

    Args:
        check: Predicate, sync or async.
        timeout: Seconds before giving up.

    Raises:
        AssertionError: If the check never passes.
    """
    deadline = time.monotonic() + timeout
    while True:
        result = check()
        if inspect.isawaitable(result):
            result = await result
        if result:
            return
        if time.monotonic() > deadline:
            msg = "condition not met before timeout"
            raise AssertionError(msg)
        await asyncio.sleep(0.2)


async def stop_workers(
    workers: list[runner.Runner], loops: list[asyncio.Task[None]]
) -> None:
    """Stop hand-driven workers the way run_workflows stops its own.

    Args:
        workers: The workers.
        loops: Their loop tasks.
    """
    for worker in workers:
        worker.stop()
    try:
        await asyncio.gather(*loops)
    finally:
        # Drained whatever a loop did, so no step outlives the test.
        for worker in workers:
            await worker.drain(datetime.timedelta(seconds=5))


def status_is(
    cls: type[
        Chain
        | Delayed
        | Flaky
        | Doomed
        | Approval
        | Slow
        | Long
        | Racer
        | Gated
        | ReviewSteps
        | Ticker
        | Batch
        | Item
        | Rendered
        | Piece
        | Ticket
    ],
    key: str,
    status: str,
) -> Callable[[], Awaitable[bool]]:
    """Build a check that a row has reached a status.

    Args:
        cls: The workflow class.
        key: The row's key.
        status: The status to wait for.

    Returns:
        An async predicate.
    """

    async def check() -> bool:
        """Tell whether the row has reached the status.

        Returns:
            Whether it has.
        """
        row = await cls.by(cls.key == key).get()
        return row is not None and row.status == status

    return check


async def test_start_runs_steps_in_order_and_ignores_duplicates(session_factory):
    key = uuid.uuid4().hex
    assert await Chain(key=key).start(Chain.first)
    assert not await Chain(key=key).start(Chain.first)
    await wait_until(status_is(Chain, key, "done"))
    row = await Chain.by(Chain.key == key).get()
    assert row is not None
    # Each of the two steps bumps the version once to claim and once to commit.
    assert (row.next_step, row.wake_at, row.wf_version) == (None, None, 4)
    assert EVENTS.count(f"first:{key}") == 1
    assert EVENTS.count(f"second:{key}") == 1


async def test_wake_in_is_queryable_and_waits(session_factory):
    key = uuid.uuid4().hex
    started = time.monotonic()
    await Delayed(key=key).start(Delayed.begin())
    await wait_until(status_is(Delayed, key, "waiting"))
    row = await Delayed.by(Delayed.key == key).get()
    assert row is not None
    assert row.next_step == "finish"
    assert row.wake_at is not None
    assert row.wake_at > datetime.datetime.now(datetime.UTC) - datetime.timedelta(
        seconds=1
    )
    await wait_until(status_is(Delayed, key, "done"))
    finished = next(e for e in EVENTS if e.startswith(f"finish:{key}:"))
    assert float(finished.rsplit(":", 1)[1]) - started >= 1


async def test_failed_step_retries_then_succeeds(session_factory):
    key = uuid.uuid4().hex
    await Flaky(key=key).start(Flaky.call())
    await wait_until(status_is(Flaky, key, "done"))
    row = await Flaky.by(Flaky.key == key).get()
    assert row is not None
    assert EVENTS.count(f"attempt:{key}") == 3
    assert (row.attempts, row.last_error) == (0, None)


async def test_exhausted_retries_stop_and_discard_the_steps_changes(session_factory):
    key = uuid.uuid4().hex
    await Doomed(key=key).start(Doomed.call())

    async def stopped() -> bool:
        """Tell whether the run has stopped.

        Returns:
            Whether it has.
        """
        row = await Doomed.by(Doomed.key == key).get()
        return row is not None and row.next_step is None

    await wait_until(stopped)
    row = await Doomed.by(Doomed.key == key).get()
    assert row is not None
    assert row.attempts == 2
    assert row.last_error == "ValueError: card declined"
    assert row.status == "new"


async def test_run_resumes_a_waiting_row_with_new_columns(session_factory):
    key = uuid.uuid4().hex
    await Approval(key=key).start(Approval.submit())
    await wait_until(status_is(Approval, key, "waiting"))
    decide = Approval.decide("yes", by="ops")
    assert await Approval.by(Approval.key == key).run(decide) == 1
    await wait_until(status_is(Approval, key, "decided:yes:ops"))
    assert await Approval.by(Approval.key == "nobody").run(decide) == 0


async def test_run_preempts_an_in_flight_step(session_factory):
    key = uuid.uuid4().hex
    await Slow(key=key).start(Slow.crawl())

    await wait_until(lambda: f"crawl-start:{key}" in EVENTS)
    await Slow.by(Slow.key == key).run(Slow.override)

    await wait_until(status_is(Slow, key, "overridden"))
    await wait_until(lambda: f"crawl-end:{key}" in EVENTS)
    await asyncio.sleep(0.5)
    row = await Slow.by(Slow.key == key).get()
    assert row is not None
    assert row.status == "overridden"


async def test_a_duplicate_execution_is_a_noop(session_factory):
    key = uuid.uuid4().hex
    await Chain(key=key).start(Chain.first)
    await wait_until(status_is(Chain, key, "done"))
    row = await Chain.by(Chain.key == key).get()
    assert row is not None
    assert await execute.execute(runtime.current(), Chain, [row.id], 0) == "stale"
    assert EVENTS.count(f"first:{key}") == 1


async def insert_due(
    factory: async_sessionmaker[AsyncSession],
    key: str,
    claimed_until: datetime.timedelta | None = None,
) -> None:
    """Write a due Chain row directly, optionally already claimed by another worker.

    Args:
        factory: Session factory.
        key: The row's key.
        claimed_until: Lease expiry relative to now; negative means already expired.
    """
    now = datetime.datetime.now(datetime.UTC)
    async with factory() as session, session.begin():
        await session.execute(
            insert(Chain).values(
                key=key,
                status="new",
                next_step="first",
                wake_at=now,
                claimed_until=now + claimed_until
                if claimed_until is not None
                else None,
                attempts=0,
                wf_version=0,
            )
        )


async def test_a_due_row_written_directly_is_picked_up(session_factory):
    key = uuid.uuid4().hex
    await insert_due(session_factory, key)
    await wait_until(status_is(Chain, key, "done"))


async def test_an_expired_lease_is_reclaimed(session_factory):
    key = uuid.uuid4().hex
    await insert_due(session_factory, key, claimed_until=-datetime.timedelta(seconds=1))
    await wait_until(status_is(Chain, key, "done"))


async def test_a_live_lease_is_not_reclaimed_until_it_expires(session_factory):
    key = uuid.uuid4().hex
    await insert_due(session_factory, key, claimed_until=datetime.timedelta(seconds=2))
    await asyncio.sleep(1)
    assert await status_is(Chain, key, "new")()
    await wait_until(status_is(Chain, key, "done"))


async def test_a_step_that_outlasts_its_lease_runs_once(session_factory):
    key = uuid.uuid4().hex
    await Long(key=key).start(Long.work)
    await wait_until(status_is(Long, key, "done"))
    assert EVENTS.count(f"long-start:{key}") == 1


async def test_competing_workers_run_each_step_once(session_factory):
    engines = [create_async_engine(ASYNC_URL) for _ in range(3)]
    workers = [
        runner.Runner(
            runtime.Runtime(
                async_sessionmaker(engine, expire_on_commit=False),
                asyncio.Event(),
                LEASE,
            ),
            [Racer],
            max_concurrency=4,
            poll_interval=datetime.timedelta(milliseconds=20),
        )
        for engine in engines
    ]
    loops = [asyncio.create_task(worker.loop()) for worker in workers]
    keys = [uuid.uuid4().hex for _ in range(60)]
    for key in keys:
        await Racer(key=key).start(Racer.go)

    async def all_done() -> bool:
        """Tell whether every run has finished.

        Returns:
            Whether it has.
        """
        return all([await status_is(Racer, key, "done")() for key in keys])

    try:
        await wait_until(all_done)
    finally:
        await stop_workers(workers, loops)
        for engine in engines:
            await engine.dispose()
    assert all(EVENTS.count(f"race:{key}") == 1 for key in keys)


async def test_a_worker_whose_lease_was_taken_over_cannot_commit(session_factory):
    key = uuid.uuid4().hex
    rt = runtime.current()
    async with session_factory() as session, session.begin():
        await session.execute(
            insert(Gated).values(
                key=key,
                status="new",
                next_step="work",
                wake_at=func.now(),
                attempts=0,
                wf_version=0,
            )
        )
    [first] = await claim.claim(rt, Gated, 1)
    pk = first.pk
    stale = asyncio.create_task(
        execute.execute(rt, Gated, pk, first.version, execute.Lease(first.until))
    )
    await wait_until(lambda: f"gated-start:{key}" in EVENTS)

    # The first worker stalls past its lease, and a second worker takes the row over.
    async with session_factory() as session, session.begin():
        await session.execute(
            update(Gated)
            .where(Gated.key == key)
            .values(claimed_until=func.now() - datetime.timedelta(seconds=1))
        )
    [second] = await claim.claim(rt, Gated, 1)
    fresh = asyncio.create_task(
        execute.execute(rt, Gated, pk, second.version, execute.Lease(second.until))
    )
    await wait_until(lambda: EVENTS.count(f"gated-start:{key}") == 2)

    # The stale worker resumes and tries to commit first; it must lose.
    GATES[1].set()
    assert await stale == "fenced"
    GATES[2].set()
    assert await fresh == "ok"
    assert await status_is(Gated, key, "done:2")()


async def test_a_delivered_event_runs_the_waiting_step_once(session_factory):
    key = uuid.uuid4().hex
    await Review(key=key).start(Review.submit())
    await wait_until(status_is(Review, key, "waiting"))
    handle = Review.by(Review.key == key)

    assert await handle.deliver(Review.decide("approve", by="ops"), key="evt-1") == 1
    await wait_until(status_is(Review, key, "decided:approve:ops"))
    assert EVENTS.count(f"decide:{key}") == 1
    row = await handle.get()
    assert row is not None
    assert (row.status, row.next_step, row.waiting_for, row.pending_event) == (
        "decided:approve:ops",
        None,
        None,
        None,
    )


async def test_an_event_that_arrives_before_the_wait_is_applied_when_it_arms(
    session_factory,
):
    key = uuid.uuid4().hex
    await Review(key=key).start(Review.submit(pause_s=1))
    await asyncio.sleep(0.3)
    assert await Review.by(Review.key == key).deliver(Review.decide("approve")) == 1
    await wait_until(status_is(Review, key, "decided:approve:manager"))
    assert f"expire:{key}" not in EVENTS


async def test_a_wait_that_times_out_runs_its_timeout_step(session_factory):
    key = uuid.uuid4().hex
    await Review(key=key).start(Review.submit(timeout_s=1))
    await wait_until(status_is(Review, key, "expired"))
    row = await Review.by(Review.key == key).get()
    assert row is not None
    assert (row.next_step, row.waiting_for, row.pending_event) == (None, None, None)


async def test_a_deadline_that_has_passed_beats_an_event(session_factory):
    key = uuid.uuid4().hex
    rt = runtime.current()
    await RaceReview(key=key).start(RaceReview.submit(timeout_s=1, expire_pause_s=2))
    pk = await arm_wait(key)

    # A worker claims the timeout, and the decision lands while it is running.
    await asyncio.sleep(1.1)
    timing_out = await claim_row(RaceReview, pk)
    expiring = asyncio.create_task(
        execute.execute(
            rt, RaceReview, pk, timing_out.version, execute.Lease(timing_out.until)
        )
    )
    await wait_until(lambda: f"expire-start:{key}" in EVENTS)
    handle = RaceReview.by(RaceReview.key == key)
    # The deadline decides when the wait ends, not whichever of the two is
    # quicker: a caller delivering faster than the workers pass would otherwise
    # put a deadline off for as long as it kept delivering.
    assert await handle.deliver(RaceReview.decide("approve")) == 0
    assert await expiring == "ok"

    assert await status_is(RaceReview, key, "expired")()
    row = await handle.get()
    assert row is not None
    assert (row.next_step, row.waiting_for, row.pending_event) == (None, None, None)


async def test_the_deadline_is_judged_as_the_delivery_reaches_the_row(
    session_factory,
):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit(timeout_s=3))
    pk = await arm_wait(key)
    handle = RaceReview.by(RaceReview.key == key)

    # Another transaction holds the row, so this delivery reaches it inside the
    # deadline and commits outside it.
    holder = create_async_engine(ASYNC_URL)
    async with holder.connect() as held:
        await held.execute(
            select(RaceReview.id)
            .where(*rows.pk_filter(RaceReview, pk))
            .with_for_update()
        )
        delivering = asyncio.create_task(handle.deliver(RaceReview.decide("approve")))
        await asyncio.sleep(4)
        assert not delivering.done()
        await held.rollback()
    await holder.dispose()

    # Taken, which is where the deadline is drawn: Postgres evaluates a volatile
    # function once as the statement starts, and the re-check it makes after
    # waiting on a lock reuses that value, so no one statement can judge the
    # deadline as it commits. Closing this needs the lock taken in a statement
    # of its own and the deadline read in the next one, which costs a round trip
    # on every delivery. Written down so a change here is a decision.
    assert await delivering == 1


async def test_an_event_inside_the_deadline_still_beats_the_timeout(session_factory):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit(timeout_s=60))
    pk = await arm_wait(key)
    handle = RaceReview.by(RaceReview.key == key)

    # Before the deadline the answer is the answer, and the timeout never runs.
    assert await handle.deliver(RaceReview.decide("approve")) == 1
    assert await step_row(RaceReview, pk) == "ok"
    assert await status_is(RaceReview, key, "decided:approve:manager")()
    assert f"expire:{key}" not in EVENTS


async def test_an_event_for_a_finished_run_is_refused(session_factory):
    key = uuid.uuid4().hex
    await Review(key=key).start(Review.submit(timeout_s=1))
    await wait_until(status_is(Review, key, "expired"))
    assert await Review.by(Review.key == key).deliver(Review.decide("approve")) == 0


async def test_a_repeat_of_a_delivered_key_is_ignored(session_factory):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit())
    handle = RaceReview.by(RaceReview.key == key)
    assert await handle.deliver(RaceReview.decide("approve"), key="evt-1") == 1

    pk = await arm_wait(key)
    # The sender retries now that the run is waiting; the first reply stands.
    assert await handle.deliver(RaceReview.decide("reject"), key="evt-1") == 0

    assert await step_row(RaceReview, pk) == "ok"
    assert await status_is(RaceReview, key, "decided:approve:manager")()
    assert EVENTS.count(f"decide:{key}") == 1


# The tables a test drives by hand, rather than leaving to a worker.
async def claim_row(
    cls: type[
        RaceReview
        | Repeating
        | Batch
        | Parked
        | Piece
        | Deferring
        | Joined
        | Leaf
        | Lingering
    ],
    pk: list[int],
) -> claim.Claimed:
    """Claim one row the way the engine does, by primary key.

    Args:
        cls: The workflow class.
        pk: The row's primary key.

    Returns:
        The version and the lease this claim holds.
    """
    stmt = (
        update(cls)
        .where(cls.id == pk[0])
        .values(claim.taking(cls, LEASE))
        .returning(cls.wf_version, cls.claimed_until)
        .execution_options(synchronize_session=False)
    )
    async with runtime.current().session_factory() as session, session.begin():
        version, until = (await session.execute(stmt)).one()
        return claim.Claimed(pk, version, until)


async def pk_of(
    cls: type[
        RaceReview | Repeating | Batch | Parked | Piece | Joined | Leaf | Lingering
    ],
    key: str,
) -> list[int]:
    """Look up a row's primary key.

    Args:
        cls: The workflow class.
        key: The row's key.

    Returns:
        The row's primary key.
    """
    row = await cls.by(cls.key == key).get()
    assert row is not None
    return [row.id]


async def step_row(
    cls: type[RaceReview | Repeating | Batch | Parked | Piece | Joined | Leaf],
    pk: list[int],
) -> str:
    """Claim and run one step of a row.

    Args:
        cls: The workflow class.
        pk: The row's primary key.

    Returns:
        The step's outcome.
    """
    taken = await claim_row(cls, pk)
    return await execute.execute(
        runtime.current(), cls, pk, taken.version, execute.Lease(taken.until)
    )


async def arm_wait(key: str) -> list[int]:
    """Run a RaceReview's first step, so the row is waiting for a decision.

    Args:
        key: The row's key.

    Returns:
        The row's primary key.
    """
    pk = await pk_of(RaceReview, key)
    assert await step_row(RaceReview, pk) == "ok"
    return pk


async def test_one_delivery_reaches_waiting_and_unstarted_runs_alike(session_factory):
    waiting, unstarted = uuid.uuid4().hex, uuid.uuid4().hex
    await RaceReview(key=waiting).start(RaceReview.submit())
    await arm_wait(waiting)
    await RaceReview(key=unstarted).start(RaceReview.submit())

    both = RaceReview.by(RaceReview.key.in_([waiting, unstarted]))
    assert await both.deliver(RaceReview.decide("approve"), key="evt-1") == 2

    armed = await RaceReview.by(RaceReview.key == waiting).get()
    assert armed is not None
    assert (armed.next_step, armed.waiting_for) == ("decide", None)
    held = await RaceReview.by(RaceReview.key == unstarted).get()
    assert held is not None
    assert held.pending_event is not None
    assert held.pending_event["step"] == "decide"


async def test_an_event_no_wait_takes_is_discarded_when_the_run_moves_on(
    session_factory,
):
    stopping, elsewhere = uuid.uuid4().hex, uuid.uuid4().hex

    # The run ends without ever waiting.
    await RaceReview(key=stopping).start(RaceReview.submit(arm=False))
    assert (
        await RaceReview.by(RaceReview.key == stopping).deliver(
            RaceReview.decide("approve")
        )
        == 1
    )

    # The run waits, but for another step than the one the event carries.
    await RaceReview(key=elsewhere).start(RaceReview.submit())
    assert (
        await RaceReview.by(RaceReview.key == elsewhere).deliver(RaceReview.expire())
        == 1
    )

    for key in (stopping, elsewhere):
        assert await step_row(RaceReview, await pk_of(RaceReview, key)) == "ok"
        row = await RaceReview.by(RaceReview.key == key).get()
        assert row is not None
        assert row.pending_event is None

    # The row that is waiting again accepts a later event for the wait it armed.
    handle = RaceReview.by(RaceReview.key == elsewhere)
    assert await handle.deliver(RaceReview.decide("approve")) == 1


async def test_a_run_refuses_a_key_it_took_before_a_newer_one(session_factory):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit())
    pk = await arm_wait(key)
    handle = RaceReview.by(RaceReview.key == key)

    # Two decisions defer, so the run waits again after each.
    for event in ("evt-1", "evt-2"):
        assert await handle.deliver(RaceReview.decide("again"), key=event) == 1
        assert await step_row(RaceReview, pk) == "ok"

    # The first sender retries; its decision was recorded two events ago.
    assert await handle.deliver(RaceReview.decide("approve"), key="evt-1") == 0
    row = await handle.get()
    assert row is not None
    assert (row.status, row.waiting_for) == ("waiting", "decide")
    assert row.recent_event_keys == ["evt-2", "evt-1"]


async def test_a_step_on_an_interval_runs_again_and_again(session_factory):
    key = uuid.uuid4().hex
    await Ticker(key=key).start(Ticker.tick)
    await wait_until(status_is(Ticker, key, "done"), timeout=10)
    assert EVENTS.count(f"tick:{key}") == 3
    row = await Ticker.by(Ticker.key == key).get()
    assert row is not None
    assert (row.next_step, row.wake_at) == (None, None)


async def insert_repeating(key: str, mode: str, due: datetime.timedelta) -> list[int]:
    """Write a Repeating row that is already due.

    Args:
        key: The row's key.
        mode: Which schedule its step repeats on.
        due: How long ago it was due.

    Returns:
        The row's primary key.
    """
    async with runtime.current().session_factory() as session, session.begin():
        await session.execute(
            insert(Repeating).values(
                key=key,
                status="new",
                next_step="tick",
                next_args={"args": [mode], "kwargs": {}},
                wake_at=func.now() - due,
                attempts=0,
                wf_version=0,
            )
        )
    return await pk_of(Repeating, key)


async def test_an_interval_keeps_its_grid_and_skips_what_was_missed(session_factory):
    key = uuid.uuid4().hex
    minute = MINUTE
    # Due nine and a half minutes ago: ten intervals on from there is still ahead.
    pk = await insert_repeating(key, "interval", datetime.timedelta(seconds=570))
    before = await Repeating.by(Repeating.key == key).get()
    assert before is not None
    assert before.wake_at is not None
    anchor = before.wake_at

    assert await step_row(Repeating, pk) == "ok"

    row = await Repeating.by(Repeating.key == key).get()
    assert row is not None
    assert row.wake_at is not None
    # One run, not one per missed minute, and the next is on the original grid.
    assert row.ticks == 1
    assert row.wake_at == anchor + 10 * minute
    assert row.wake_at > datetime.datetime.now(datetime.UTC)


async def test_a_cron_schedule_sets_the_next_time_it_names(session_factory):
    key = uuid.uuid4().hex
    pk = await insert_repeating(key, "cron", datetime.timedelta(seconds=1))
    assert await step_row(Repeating, pk) == "ok"

    row = await Repeating.by(Repeating.key == key).get()
    assert row is not None
    assert row.wake_at is not None
    wake_at = row.wake_at.astimezone(datetime.UTC)
    now = datetime.datetime.now(datetime.UTC)
    assert (wake_at.minute, wake_at.second) == (0, 0)
    assert now < wake_at <= now + datetime.timedelta(hours=1)


async def test_a_schedule_that_cannot_say_when_stops_the_run(session_factory):
    key = uuid.uuid4().hex
    pk = await insert_repeating(key, "broken", datetime.timedelta(seconds=1))
    assert await step_row(Repeating, pk) == "failed"

    row = await Repeating.by(Repeating.key == key).get()
    assert row is not None
    assert (row.next_step, row.wake_at) == (None, None)
    assert row.last_error == "RuntimeError: no idea when"
    # The attempt's history says why, as the row does.
    async with runtime.current().session_factory() as session:
        latest = (
            await session.execute(
                select(WorkflowAttempt)
                .where(
                    WorkflowAttempt.workflow == "wf_test_repeating",
                    WorkflowAttempt.run == pk,
                )
                .order_by(WorkflowAttempt.id.desc())
                .limit(1)
            )
        ).scalar_one()
    assert (latest.outcome, latest.error) == ("failed", row.last_error)
    # The step itself ran once; it was its schedule that failed.
    assert latest.attempt == 1


async def test_a_run_can_buffer_another_event_after_one_was_consumed(session_factory):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit())
    handle = RaceReview.by(RaceReview.key == key)

    # One event is buffered, armed, and consumed, which clears the buffer.
    assert await handle.deliver(RaceReview.decide("again"), key="evt-1") == 1
    pk = await pk_of(RaceReview, key)
    assert await step_row(RaceReview, pk) == "ok"
    assert await step_row(RaceReview, pk) == "ok"
    row = await handle.get()
    assert row is not None
    assert (row.waiting_for, row.pending_event) == ("decide", None)

    # The next event applies, leaving the run scheduled rather than waiting.
    assert await handle.deliver(RaceReview.decide("again"), key="evt-2") == 1
    row = await handle.get()
    assert row is not None
    assert (row.next_step, row.waiting_for) == ("decide", None)

    # A third event arrives before that step runs: the cleared buffer is free.
    assert await handle.deliver(RaceReview.decide("approve"), key="evt-3") == 1
    row = await handle.get()
    assert row is not None
    assert row.pending_event is not None


async def test_a_fan_out_runs_its_children_and_reports_once_they_are_done(
    session_factory,
):
    key = uuid.uuid4().hex
    await Batch(key=key, size=4).start(Batch.split())
    await wait_until(status_is(Batch, key, "reported"))

    row = await Batch.by(Batch.key == key).get()
    assert row is not None
    assert (row.done, row.children_left) == (4, 0)
    assert EVENTS.count(f"split:{key}") == 1
    assert [EVENTS.count(f"item:{key}-{index}") for index in range(4)] == [1] * 4
    items = await row.children(Item).all()
    assert len(items) == 4
    # Each still points at the parent, which is what finds them again, and none
    # still names the fan-out it was counted toward.
    assert all(item.parent == row.as_parent() for item in items)


async def test_children_run_at_the_same_time(session_factory):
    key = uuid.uuid4().hex
    ITEMS["peak"] = 0
    await Batch(key=key, size=6).start(Batch.split())
    await wait_until(status_is(Batch, key, "reported"))

    # Several were in their step together, which is the point of fanning out.
    assert ITEMS["peak"] >= 3


async def test_a_child_that_gives_up_still_releases_the_parent(session_factory):
    key = uuid.uuid4().hex
    await Batch(key=key, size=3, failures=1).start(Batch.split())
    await wait_until(status_is(Batch, key, "reported"))

    row = await Batch.by(Batch.key == key).get()
    assert row is not None
    # Two of the three finished; the parent still ran, and says so.
    assert (row.done, row.children_left) == (2, 0)
    failed = await Item.by(Item.key == f"{key}-0").get()
    assert failed is not None
    assert failed.last_error == "RuntimeError: item gave up"


async def test_a_parent_waits_while_its_children_run(session_factory):
    key = uuid.uuid4().hex
    await Parked(key=key, size=3).start(Parked.split)
    parent = await pk_of(Parked, key)
    assert await step_row(Parked, parent) == "ok"

    # Nothing runs these tables but this test, so the parked state stands still:
    # scheduled to report, with nothing to wake it and three children out.
    row = await Parked.by(Parked.key == key).get()
    assert row is not None
    assert (row.next_step, row.wake_at, row.children_left) == ("report", None, 3)

    for index in range(3):
        piece = await pk_of(Piece, f"{key}-{index}")
        assert await step_row(Piece, piece) == "ok"
        row = await Parked.by(Parked.key == key).get()
        assert row is not None
        assert row.children_left == 2 - index
        # Only the last one to finish makes the parent due.
        assert (row.wake_at is None) == (index < 2)

    assert await step_row(Parked, parent) == "ok"
    row = await Parked.by(Parked.key == key).get()
    assert row is not None
    assert (row.status, row.done) == ("reported", 3)


async def test_a_fan_out_that_loses_its_row_starts_no_children(session_factory):
    key = uuid.uuid4().hex
    rt = runtime.current()
    async with session_factory() as session, session.begin():
        await session.execute(
            insert(Batch).values(
                key=key,
                size=3,
                status="new",
                next_step="split",
                next_args={"args": [], "kwargs": {"pause_s": 0.5}},
                wake_at=func.now(),
                attempts=0,
                wf_version=0,
            )
        )
    row = await Batch.by(Batch.key == key).get()
    assert row is not None
    pk = [row.id]

    # The row is taken over while the step runs, so its commit is refused. The
    # children go in with that commit, so they must be refused with it.
    claimed = await claim_row(Batch, pk)
    splitting = asyncio.create_task(
        execute.execute(rt, Batch, pk, claimed.version, execute.Lease(claimed.until))
    )
    await wait_until(lambda: f"split:{key}" in EVENTS)
    await claim_row(Batch, pk)
    assert await splitting == "fenced"

    await asyncio.sleep(0.3)
    assert await Item.by(Item.key == f"{key}-0").get() is None
    started = await Batch.by(Batch.key == key).get()
    assert started is not None
    assert started.children_left is None


async def start_many(cls, prefix: str, count: int, **columns) -> list[str]:
    """Start a number of runs of one workflow.

    Args:
        cls: The workflow class.
        prefix: What to name them.
        count: How many to start.
        **columns: The other columns each row carries.

    Returns:
        The keys of the runs started.
    """
    keys = [f"{prefix}-{index}" for index in range(count)]
    for key in keys:
        await cls(key=key, **columns).start(cls.work)
    return keys


async def test_one_customer_cannot_run_more_than_its_limit(session_factory):
    LIVE.clear()
    PEAK.clear()
    busy, small = f"busy-{uuid.uuid4().hex}", f"small-{uuid.uuid4().hex}"
    await start_many(Tenant, busy, 8, customer=busy)
    await start_many(Tenant, small, 2, customer=small)

    async def all_done() -> bool:
        """Tell whether every run has finished.

        Returns:
            Whether it has.
        """
        rows = await Tenant.by(Tenant.customer.in_([busy, small])).all()
        return len(rows) == 10 and all(row.status == "done" for row in rows)

    await wait_until(all_done, timeout=60)
    # Two at a time each, however many rows were waiting and however free the
    # workers were.
    assert PEAK[busy] == 2
    assert PEAK[small] <= 2


async def test_a_busy_customer_does_not_starve_a_quiet_one(session_factory):
    LIVE.clear()
    PEAK.clear()
    flood, one = f"flood-{uuid.uuid4().hex}", f"one-{uuid.uuid4().hex}"
    await start_many(Tenant, flood, 20, customer=flood)
    started = time.monotonic()
    await start_many(Tenant, one, 1, customer=one)

    async def quiet_done() -> bool:
        """Tell whether the quiet customer's run has finished.

        Returns:
            Whether it has.
        """
        row = await Tenant.by(Tenant.key == f"{one}-0").get()
        return row is not None and row.status == "done"

    await wait_until(quiet_done, timeout=30)
    # The flood is still going; the single row did not wait behind all of it.
    assert time.monotonic() - started < 5
    assert PEAK[flood] == 2


async def test_a_limit_holds_across_workers(session_factory):
    LIVE.clear()
    PEAK.clear()
    engines = [create_async_engine(ASYNC_URL) for _ in range(3)]
    workers = [
        runner.Runner(
            runtime.Runtime(
                async_sessionmaker(engine, expire_on_commit=False),
                asyncio.Event(),
                LEASE,
            ),
            [Tenant],
            max_concurrency=8,
            poll_interval=datetime.timedelta(milliseconds=20),
        )
        for engine in engines
    ]
    loops = [asyncio.create_task(worker.loop()) for worker in workers]
    customer = f"shared-{uuid.uuid4().hex}"
    keys = await start_many(Tenant, customer, 12, customer=customer)

    async def all_done() -> bool:
        """Tell whether every run has finished.

        Returns:
            Whether it has.
        """
        rows = await Tenant.by(Tenant.key.in_(keys)).all()
        return len(rows) == len(keys) and all(row.status == "done" for row in rows)

    try:
        await wait_until(all_done, timeout=60)
    finally:
        await stop_workers(workers, loops)
        for engine in engines:
            await engine.dispose()

    # Three workers, twenty-four free slots between them, two rows at a time.
    assert PEAK[customer] == 2


async def test_a_backlogged_table_does_not_hold_up_another(session_factory):
    key = uuid.uuid4().hex
    await start_many(Noisy, f"noise-{key}", 40)
    started = time.monotonic()
    await Quiet(key=key).start(Quiet.work)

    await wait_until(lambda: f"quiet:{key}" in EVENTS, timeout=30)
    assert time.monotonic() - started < 5


async def test_a_worker_with_one_slot_still_visits_every_table(session_factory):
    key = uuid.uuid4().hex
    await start_many(Hog, f"hog-{key}", 30)
    await Tiny(key=key).start(Tiny.work)

    # One slot between two tables, and no other worker runs these two: without
    # taking the tables in turn, the backlog holds that slot every pass and the
    # single row waits for all thirty.
    engine = create_async_engine(ASYNC_URL)
    worker = runner.Runner(
        runtime.Runtime(
            async_sessionmaker(engine, expire_on_commit=False),
            asyncio.Event(),
            LEASE,
        ),
        [Hog, Tiny],
        max_concurrency=1,
        poll_interval=datetime.timedelta(milliseconds=20),
    )
    loop = asyncio.create_task(worker.loop())
    try:
        await wait_until(lambda: f"tiny:{key}" in EVENTS, timeout=20)
        backlog = await Hog.by(Hog.key.startswith(f"hog-{key}")).all()
        assert sum(row.status == "done" for row in backlog) < 5
    finally:
        await stop_workers([worker], [loop])
        await engine.dispose()


@pytest.mark.parametrize("enqueue_delay", [0, 1.1])
async def test_a_rate_limit_lets_through_a_burst_then_refills(
    session_factory, monkeypatch, enqueue_delay
):
    """A full bucket allows a burst and a partial refill allows two more runs."""
    STARTS.clear()
    provider = f"provider-{uuid.uuid4().hex}"
    # Four tokens per hour prevent setup or scheduling delays from refilling
    # the bucket; backdating it by half an hour releases exactly two tokens.
    period = datetime.timedelta(hours=1)
    monkeypatch.setattr(
        Metered, "__workflow_limit__", Limit(by="provider", rate=4, per=period)
    )
    await asyncio.sleep(enqueue_delay)
    await start_many(Metered, provider, 8, provider=provider)

    for expected in (4, 6, 8):
        if expected > 4:
            async with session_factory() as session, session.begin():
                await session.execute(
                    update(WorkflowRate)
                    .where(WorkflowRate.key == claim.bucket_key(Metered, provider))
                    .values(tokens=0, updated_at=func.now() - period / 2)
                )
        # A settled worker has finished its steps and found no more to claim.
        assert await runner.wake(datetime.timedelta(seconds=30))
        assert len(STARTS[provider]) == expected
        rows = await Metered.by(Metered.provider == provider).all()
        assert len(rows) == 8
        assert sum(row.status == "done" for row in rows) == expected


async def test_a_rate_limit_holds_across_workers(session_factory):
    STARTS.clear()
    provider = f"shared-{uuid.uuid4().hex}"
    engines = [create_async_engine(ASYNC_URL) for _ in range(3)]
    workers = [
        runner.Runner(
            runtime.Runtime(
                async_sessionmaker(engine, expire_on_commit=False),
                asyncio.Event(),
                LEASE,
            ),
            [Metered],
            max_concurrency=8,
            poll_interval=datetime.timedelta(milliseconds=20),
        )
        for engine in engines
    ]
    loops = [asyncio.create_task(worker.loop()) for worker in workers]
    started = time.monotonic()
    await start_many(Metered, provider, 6, provider=provider)

    async def all_done() -> bool:
        """Tell whether every run has finished.

        Returns:
            Whether it has.
        """
        rows = await Metered.by(Metered.provider == provider).all()
        return len(rows) == 6 and all(row.status == "done" for row in rows)

    try:
        await wait_until(all_done, timeout=60)
    finally:
        await stop_workers(workers, loops)
        for engine in engines:
            await engine.dispose()

    times = sorted(t - started for t in STARTS[provider])
    # Three workers, twenty-four slots, one bucket: the sixth still waits for
    # the two it takes to refill past the burst.
    assert len(times) == 6
    assert times[5] >= 0.9


async def test_two_providers_do_not_spend_each_others_tokens(session_factory):
    STARTS.clear()
    one, two = f"one-{uuid.uuid4().hex}", f"two-{uuid.uuid4().hex}"
    started = time.monotonic()
    await start_many(Metered, one, 8, provider=one)
    await start_many(Metered, two, 3, provider=two)

    async def second_done() -> bool:
        """Tell whether the second provider's runs have finished.

        Returns:
            Whether it has.
        """
        rows = await Metered.by(Metered.provider == two).all()
        return len(rows) == 3 and all(row.status == "done" for row in rows)

    await wait_until(second_done, timeout=30)
    # The quiet provider's three came straight out of its own full bucket.
    assert max(t - started for t in STARTS[two]) < 1


def lane_worker(lanes, workflows=(Rendered,), concurrency=4):
    """Build a worker serving particular lanes.

    Args:
        lanes: The lanes it serves.
        workflows: The workflow classes it runs.
        concurrency: How many steps it runs at once.

    Returns:
        The runner and the engine behind it.
    """
    engine = create_async_engine(ASYNC_URL)
    worker = runner.Runner(
        runtime.Runtime(
            async_sessionmaker(engine, expire_on_commit=False),
            asyncio.Event(),
            LEASE,
        ),
        list(workflows),
        max_concurrency=concurrency,
        poll_interval=datetime.timedelta(milliseconds=20),
        # Nothing listens for these, and a deaf worker now waits like any
        # other; in production that ear is what the wait is long for. These
        # stand in for workers that have one, so they look as often as they
        # poll.
        max_idle_interval=datetime.timedelta(milliseconds=20),
        lanes=lanes,
    )
    return worker, engine


@contextlib.asynccontextmanager
async def lane_workers(*lane_sets):
    """Run a worker per set of lanes for the length of the block.

    Args:
        *lane_sets: The lanes each worker serves.

    Yields:
        Nothing; the workers run while the block is active.
    """
    made = [lane_worker(lanes) for lanes in lane_sets]
    loops = [asyncio.create_task(worker.loop()) for worker, _ in made]
    try:
        yield
    finally:
        await stop_workers([worker for worker, _ in made], loops)
        for _, engine in made:
            await engine.dispose()


async def test_a_step_in_a_lane_waits_for_a_worker_that_serves_it(session_factory):
    key = uuid.uuid4().hex
    async with lane_workers(["default"]):
        await Rendered(key=key).start(Rendered.prepare)
        await wait_until(status_is(Rendered, key, "prepared"))
        # The ordinary worker did its part and left the rest alone.
        await asyncio.sleep(0.5)
        assert f"render:{key}" not in EVENTS

    row = await Rendered.by(Rendered.key == key).get()
    assert row is not None
    assert (row.next_step, row.claimed_until) == ("render", None)

    async with lane_workers(["gpu"]):
        await wait_until(status_is(Rendered, key, "rendered"))
    assert EVENTS.count(f"render:{key}") == 1


async def test_workers_of_each_kind_carry_one_run_between_them(session_factory):
    key = uuid.uuid4().hex
    async with lane_workers(["default"], ["gpu"]):
        await Rendered(key=key).start(Rendered.prepare)
        await wait_until(status_is(Rendered, key, "rendered"))

        # The wait is for a step in the gpu lane, so only that worker takes it.
        assert await Rendered.by(Rendered.key == key).deliver(Rendered.collect()) == 1
        await wait_until(status_is(Rendered, key, "collected"))

    assert [
        EVENTS.count(f"{name}:{key}") for name in ("prepare", "render", "collect")
    ] == [1, 1, 1]


async def test_a_row_holding_an_event_for_a_laned_step_waits_for_that_lane(
    session_factory,
):
    key = uuid.uuid4().hex
    # The state the engine leaves when an event arrives before its wait arms:
    # nothing scheduled, waiting on a gpu step, and the event already in hand.
    async with session_factory() as session, session.begin():
        await session.execute(
            insert(Rendered).values(
                key=key,
                status="rendered",
                next_step=None,
                wake_at=None,
                waiting_for="collect",
                pending_event={"step": "collect", "args": {"args": [], "kwargs": {}}},
                attempts=0,
                wf_version=0,
            )
        )

    async with lane_workers(["default"]):
        await asyncio.sleep(0.5)
        # It is ready to run, but not by this worker.
        assert f"collect:{key}" not in EVENTS

    async with lane_workers(["gpu"]):
        await wait_until(status_is(Rendered, key, "collected"))
    assert EVENTS.count(f"collect:{key}") == 1


async def test_a_held_event_beats_a_due_timeout_in_another_lane(session_factory):
    key = uuid.uuid4().hex
    # Waiting on a gpu step with its event in hand, and the timeout, a step in
    # the default lane, due as well: the default worker may run neither.
    async with session_factory() as session, session.begin():
        await session.execute(
            insert(Rendered).values(
                key=key,
                status="rendered",
                next_step="prepare",
                next_args={"args": [], "kwargs": {}},
                wake_at=func.now(),
                waiting_for="collect",
                pending_event={"step": "collect", "args": {"args": [], "kwargs": {}}},
                attempts=0,
                wf_version=0,
            )
        )

    async with lane_workers(["default"]):
        await asyncio.sleep(0.5)
        assert f"collect:{key}" not in EVENTS
        assert f"prepare:{key}" not in EVENTS

    async with lane_workers(["gpu"]):
        await wait_until(status_is(Rendered, key, "collected"))
    assert EVENTS.count(f"collect:{key}") == 1
    assert f"prepare:{key}" not in EVENTS


async def test_a_worker_does_not_wait_on_a_held_event_another_lane_will_take(
    session_factory,
):
    await Rendered.by().cancel()
    key = uuid.uuid4().hex
    # Waiting on a gpu step with its event in hand, and the timeout, a step in
    # the default lane, overdue.
    async with session_factory() as session, session.begin():
        await session.execute(
            insert(Rendered).values(
                key=key,
                status="rendered",
                next_step="prepare",
                next_args={"args": [], "kwargs": {}},
                wake_at=func.now() - datetime.timedelta(minutes=5),
                waiting_for="collect",
                pending_event={"step": "collect", "args": {"args": [], "kwargs": {}}},
                attempts=0,
                wf_version=0,
            )
        )
    rt = runtime.current()
    lanes: dict[str, dict[type[Workflow], list[str] | None]] = {
        lane: {Rendered: model.steps_in(Rendered, [lane])}
        for lane in ("default", "gpu")
    }
    # The default worker can claim nothing here, so it has nothing to wait for:
    # an overdue answer would have it look again every poll interval for good.
    assert await claim.next_due(rt, [Rendered], lanes["default"]) is None
    # The gpu worker can take the event now.
    due = await claim.next_due(rt, [Rendered], lanes["gpu"])
    assert due is not None
    assert due.away <= datetime.timedelta()
    await Rendered.by(Rendered.key == key).cancel()


async def test_a_worker_serving_both_lanes_runs_the_whole_thing(session_factory):
    key = uuid.uuid4().hex
    async with lane_workers(["default", "gpu"]):
        await Rendered(key=key).start(Rendered.prepare)
        await wait_until(status_is(Rendered, key, "rendered"))
    assert EVENTS.count(f"prepare:{key}") == 1
    assert EVENTS.count(f"render:{key}") == 1


async def test_a_worker_skips_a_table_it_can_run_nothing_of(session_factory):
    worker, engine = lane_worker(["gpu"], workflows=(Chain, Rendered))
    try:
        # Chain has no step in the gpu lane, so the worker does not visit it.
        assert worker.workflows == [Rendered]
        assert worker.runnable[Rendered] == ["render", "collect"]
    finally:
        await engine.dispose()


async def test_a_process_can_address_runs_without_running_them(session_factory):
    key = uuid.uuid4().hex
    engine = create_async_engine(ASYNC_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        # A web process: no worker of its own, and no worker anywhere runs this
        # table, so the run it starts stays where it is put.
        async with runner.connect_workflows(factory):
            assert await Piece(key=key).start(Piece.work)
            row = await Piece.by(Piece.key == key).get()
            assert row is not None
            assert (row.next_step, row.status) == ("work", "new")

            await asyncio.sleep(0.3)
            still = await Piece.by(Piece.key == key).get()
            assert still is not None
            assert (still.next_step, still.claimed_until) == ("work", None)
    finally:
        await engine.dispose()

    # A worker that does run it finds it waiting on its next pass.
    worker, worker_engine = lane_worker(["default"], workflows=(Piece,))
    loop = asyncio.create_task(worker.loop())
    try:
        await wait_until(status_is(Piece, key, "done"))
    finally:
        await stop_workers([worker], [loop])
        await worker_engine.dispose()


async def test_connecting_inside_a_running_worker_leaves_it_running(session_factory):
    key = uuid.uuid4().hex
    engine = create_async_engine(ASYNC_URL)
    try:
        async with runner.connect_workflows(
            async_sessionmaker(engine, expire_on_commit=False)
        ):
            assert await Chain(key=key).start(Chain.first)
    finally:
        await engine.dispose()

    # The fixture's worker is still the engine in this process afterwards.
    await wait_until(status_is(Chain, key, "done"))
    assert await Chain(key=f"{key}-after").start(Chain.first)
    await wait_until(status_is(Chain, f"{key}-after", "done"))


async def test_addressing_runs_with_nothing_set_up_says_what_to_enter():
    previous = runtime.replace_current(None)
    try:
        with pytest.raises(RuntimeError, match="connect_workflows"):
            await Chain.by(Chain.key == "nobody").get()
    finally:
        runtime.replace_current(previous)


@contextlib.asynccontextmanager
async def slow_worker(workflows, poll: datetime.timedelta):
    """Run a worker that would almost never poll, to see what wakes it.

    Args:
        workflows: The workflow classes it runs.
        poll: How long it waits between passes when nothing wakes it.

    Yields:
        Nothing; the worker runs while the block is active.
    """
    engine = create_async_engine(ASYNC_URL)
    async with run_workflows(
        async_sessionmaker(engine, expire_on_commit=False),
        workflows=list(workflows),
        poll_interval=poll,
        lease=LEASE,
    ):
        yield
    await engine.dispose()


async def test_a_worker_hears_about_work_started_by_another_process(session_factory):
    key = uuid.uuid4().hex
    patient = datetime.timedelta(seconds=30)
    async with slow_worker([Piece], patient):
        # Let it finish its first pass and settle into that long wait, so what
        # wakes it is the news and not a pass that had not happened yet.
        await asyncio.sleep(0.5)
        started = time.monotonic()
        # A different connection entirely, as another process would be.
        engine = create_async_engine(ASYNC_URL)
        try:
            async with runner.connect_workflows(
                async_sessionmaker(engine, expire_on_commit=False)
            ):
                assert await Piece(key=key).start(Piece.work)
        finally:
            await engine.dispose()

        await wait_until(status_is(Piece, key, "done"), timeout=20)
        # Polling would have taken half a minute.
        assert time.monotonic() - started < 5


async def test_a_worker_hears_about_an_event_delivered_elsewhere(session_factory):
    key = uuid.uuid4().hex
    patient = datetime.timedelta(seconds=30)
    async with slow_worker([RaceReview], patient):
        await RaceReview(key=key).start(RaceReview.submit())
        await wait_until(status_is(RaceReview, key, "waiting"), timeout=20)

        started = time.monotonic()
        engine = create_async_engine(ASYNC_URL)
        try:
            async with runner.connect_workflows(
                async_sessionmaker(engine, expire_on_commit=False)
            ):
                assert (
                    await RaceReview.by(RaceReview.key == key).deliver(
                        RaceReview.decide("approve")
                    )
                    == 1
                )
        finally:
            await engine.dispose()

        await wait_until(
            status_is(RaceReview, key, "decided:approve:manager"), timeout=20
        )
        assert time.monotonic() - started < 5


async def test_a_worker_ignores_news_about_tables_it_does_not_run(session_factory):
    engine = create_async_engine(ASYNC_URL)
    rt = runtime.Runtime(
        async_sessionmaker(engine, expire_on_commit=False), asyncio.Event(), LEASE
    )
    ear = asyncio.create_task(notify.wake_on_notify(rt, ["wf_test_piece"]))
    try:
        await asyncio.sleep(0.3)
        async with rt.session_factory() as session, session.begin():
            await notify.announce(session, "wf_test_chain")
        await asyncio.sleep(0.5)
        assert not rt.wake.is_set()

        async with rt.session_factory() as session, session.begin():
            await notify.announce(session, "wf_test_piece")
        await wait_until(rt.wake.is_set, timeout=10)
    finally:
        ear.cancel()
        await asyncio.gather(ear, return_exceptions=True)
        await engine.dispose()


async def test_a_run_records_what_each_step_did(session_factory):
    key = uuid.uuid4().hex
    await Chain(key=key).start(Chain.first)
    await wait_until(status_is(Chain, key, "done"))

    row = await Chain.by(Chain.key == key).get()
    assert row is not None
    history = await row.history()
    # Newest first: the second step, then the first.
    assert [(a.step, a.outcome) for a in history] == [
        ("second", "ok"),
        ("first", "ok"),
    ]
    assert all(a.error is None and a.took_ms >= 0 for a in history)
    assert all(a.workflow == "wf_test_chain" and a.run == [row.id] for a in history)


async def test_a_run_keyed_by_more_than_json_holds_commits_and_is_recorded(
    session_factory,
):
    tenant, key = uuid.uuid4(), uuid.uuid4().hex
    await Ticket(tenant=tenant, number=7, key=key).start(Ticket.work)
    await wait_until(status_is(Ticket, key, "done"))

    row = await Ticket.by(Ticket.key == key).get()
    assert row is not None
    history = await row.history()
    # The key is stored as the text it reads back from, column by column, so
    # writing the history cannot refuse the step's own commit alongside it.
    assert [a.run for a in history] == [[str(tenant), 7]]
    assert [(a.step, a.outcome) for a in history] == [("work", "ok")]


async def test_a_fan_out_joins_up_when_its_keys_are_more_than_json_holds(
    session_factory,
):
    start = datetime.datetime.now(datetime.UTC)
    await Window(at=start).start(Window.split)

    async def gathered() -> bool:
        """Tell whether the window has joined up with its slots.

        Returns:
            Whether it has.
        """
        row = await Window.by(Window.at == start).get()
        return row is not None and row.status == "gathered"

    await wait_until(gathered)
    # Each child pointed back at a parent it could only name as text, and the
    # count that releases the parent found it again through that pointer.
    slots = await Slot.by(Slot.at.in_([slot_at(start, n) for n in (1, 2)])).all()
    assert sorted(slot.status for slot in slots) == ["filled", "filled"]
    row = await Window.by(Window.at == start).get()
    assert row is not None
    assert row.children_left == 0


async def test_history_keeps_every_attempt_of_a_step_that_was_retried(session_factory):
    key = uuid.uuid4().hex
    await Flaky(key=key).start(Flaky.call())
    await wait_until(status_is(Flaky, key, "done"))

    row = await Flaky.by(Flaky.key == key).get()
    assert row is not None
    history = list(reversed(await row.history()))
    # Two failures and the attempt that worked, in the order they happened.
    assert [(a.attempt, a.outcome) for a in history] == [
        (1, "retry"),
        (2, "retry"),
        (3, "ok"),
    ]
    assert history[0].error == "ConnectionError: provider timed out"
    assert history[-1].error is None


async def test_history_records_a_run_that_gave_up(session_factory):
    key = uuid.uuid4().hex
    await Doomed(key=key).start(Doomed.call())

    async def stopped() -> bool:
        """Tell whether the run has stopped.

        Returns:
            Whether it has.
        """
        row = await Doomed.by(Doomed.key == key).get()
        return row is not None and row.next_step is None

    await wait_until(stopped)
    row = await Doomed.by(Doomed.key == key).get()
    assert row is not None
    history = await row.history()
    assert [a.outcome for a in history] == ["failed", "retry"]
    assert all(a.error == "ValueError: card declined" for a in history)


async def test_an_attempt_whose_commit_was_refused_is_not_recorded(session_factory):
    key = uuid.uuid4().hex
    rt = runtime.current()
    await RaceReview(key=key).start(RaceReview.submit(pause_s=0.5))
    pk = await pk_of(RaceReview, key)

    # The row is taken over while the step runs, so its commit is refused.
    claimed = await claim_row(RaceReview, pk)
    running = asyncio.create_task(
        execute.execute(
            rt, RaceReview, pk, claimed.version, execute.Lease(claimed.until)
        )
    )
    await asyncio.sleep(0.2)
    await claim_row(RaceReview, pk)
    assert await running == "fenced"

    row = await RaceReview.by(RaceReview.key == key).get()
    assert row is not None
    # It ran, but nothing it did was kept, so there is nothing to record.
    assert await row.history() == []


async def test_history_is_only_written_when_a_table_is_mapped(
    session_factory, monkeypatch
):
    key = uuid.uuid4().hex
    monkeypatch.setattr(model, "ATTEMPTS", None)
    await Chain(key=key).start(Chain.first)
    await wait_until(status_is(Chain, key, "done"))

    async with session_factory() as session:
        written = (
            (
                await session.execute(
                    select(WorkflowAttempt).where(
                        WorkflowAttempt.workflow == "wf_test_chain"
                    )
                )
            )
            .scalars()
            .all()
        )
    row = await Chain.by(Chain.key == key).get()
    assert row is not None
    assert all(attempt.run != [row.id] for attempt in written)


async def test_a_worker_stopping_mid_claim_runs_what_it_claimed(
    session_factory, monkeypatch
):
    keys = await start_many(Parting, f"parting-{uuid.uuid4().hex}", 4)
    claimed_rows, release = asyncio.Event(), asyncio.Event()
    real_claim = runner.claim

    async def claim_then_pause(runtime_, cls, limit, steps=None):
        """Claim, then pause once Parting rows are leased but not yet started.

        Args:
            runtime_: The running engine.
            cls: The workflow class.
            limit: Most rows to claim.
            steps: The steps the worker may run.

        Returns:
            What the claim took.
        """
        claimed = await real_claim(runtime_, cls, limit, steps)
        if cls is Parting and claimed:
            # The rows are leased and committed; the worker has not started them.
            claimed_rows.set()
            await release.wait()
        return claimed

    monkeypatch.setattr(runner, "claim", claim_then_pause)
    worker = run_workflows(
        session_factory,
        workflows=[Parting],
        poll_interval=datetime.timedelta(milliseconds=50),
        lease=datetime.timedelta(minutes=5),
    )
    await worker.__aenter__()
    stopping = None
    try:
        await asyncio.wait_for(claimed_rows.wait(), 30)
        # The worker is told to stop while its claim is still returning.
        stopping = asyncio.create_task(worker.__aexit__(None, None, None))
        await asyncio.sleep(0.2)
    finally:
        # Whatever happened above, the worker stops and the runtime is restored.
        release.set()
        await (stopping or worker.__aexit__(None, None, None))

    rows = await Parting.by(Parting.key.in_(keys)).all()
    taken = [
        row for row in rows if row.claimed_until is not None or row.status == "done"
    ]
    # Whatever it leased, it ran: nothing waits out a five-minute lease.
    assert taken
    assert all(row.status == "done" and row.claimed_until is None for row in taken)


async def test_run_abandons_a_wait_and_the_event_held_for_it(session_factory):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit())
    pk = await arm_wait(key)
    handle = RaceReview.by(RaceReview.key == key)

    assert await handle.run(RaceReview.expire()) == 1
    # A decision for the wait that was abandoned no longer takes the run over.
    await handle.deliver(RaceReview.decide("approve"))
    assert await step_row(RaceReview, pk) == "ok"

    row = await handle.get()
    assert row is not None
    assert (row.status, row.waiting_for, row.pending_event) == ("expired", None, None)


async def test_a_step_asked_for_while_a_timeout_runs_waits_for_it_to_end(
    session_factory,
):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit(timeout_s=0, expire_pause_s=1))
    pk = await arm_wait(key)
    expiring = asyncio.create_task(step_row(RaceReview, pk))
    await wait_until(lambda: f"expire-start:{key}" in EVENTS, timeout=10)

    handle = RaceReview.by(RaceReview.key == key)
    # Asked for rather than delivered: past its deadline this wait refuses
    # events, so ``run`` is what preempts a timeout that is already going.
    assert await handle.run(RaceReview.decide("approve")) == 1
    row = await handle.get()
    assert row is not None
    # The expiry still holds the row, so the decision cannot run beside it.
    assert row.next_step == "decide"
    assert row.claimed_until is not None

    # Fenced, the expiry gives its lease back rather than making the decision
    # wait out the rest of it.
    assert await expiring == "fenced"
    row = await handle.get()
    assert row is not None
    assert row.claimed_until is None
    assert await step_row(RaceReview, pk) == "ok"


async def test_a_step_gives_back_only_its_own_lease(session_factory):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit())
    pk = await pk_of(RaceReview, key)
    # Another worker holds the row now, with a lease of its own.
    await claim_row(RaceReview, pk)
    theirs = await RaceReview.by(RaceReview.key == key).get()
    assert theirs is not None
    assert theirs.claimed_until is not None

    stale = execute.Lease(theirs.claimed_until - datetime.timedelta(minutes=5))
    await execute.release(runtime.current(), RaceReview, pk, stale)
    row = await RaceReview.by(RaceReview.key == key).get()
    assert row is not None
    assert row.claimed_until == theirs.claimed_until


async def test_an_event_held_while_a_step_ran_is_dropped_when_nothing_can_take_it(
    session_factory,
):
    ending, elsewhere = uuid.uuid4().hex, uuid.uuid4().hex
    await RaceReview(key=ending).start(RaceReview.submit(pause_s=0.5, arm=False))
    await RaceReview(key=elsewhere).start(RaceReview.submit(pause_s=0.5))

    for key, event in (
        (ending, RaceReview.decide("approve")),
        (elsewhere, RaceReview.expire()),
    ):
        running = asyncio.create_task(
            step_row(RaceReview, await pk_of(RaceReview, key))
        )
        await asyncio.sleep(0.2)
        # Lands while the step runs, after it read the row.
        assert await RaceReview.by(RaceReview.key == key).deliver(event) == 1
        assert await running == "ok"
        row = await RaceReview.by(RaceReview.key == key).get()
        assert row is not None
        assert row.pending_event is None

    # The run waiting again takes the next event for the wait it armed.
    handle = RaceReview.by(RaceReview.key == elsewhere)
    assert await handle.deliver(RaceReview.decide("approve")) == 1


async def test_a_child_run_again_does_not_release_its_parent_again(session_factory):
    key = uuid.uuid4().hex
    await Batch(key=key, size=2).start(Batch.split())
    await wait_until(status_is(Batch, key, "reported"))

    assert await Item.by(Item.key == f"{key}-0").run(Item.work()) == 1
    await wait_until(lambda: EVENTS.count(f"item:{key}-0") == 2)
    await asyncio.sleep(0.5)

    row = await Batch.by(Batch.key == key).get()
    assert row is not None
    assert row.children_left == 0


async def test_a_child_of_an_abandoned_fan_out_does_not_count_toward_the_next(
    session_factory,
):
    key = uuid.uuid4().hex
    await Parked(key=key, size=2).start(Parked.split)
    parent = await pk_of(Parked, key)
    assert await step_row(Parked, parent) == "ok"

    # The parent is moved on before its pieces finish, and fans out again with
    # one more piece: pieces 0 and 1 are there already, so only piece 2 is new.
    async with session_factory() as session, session.begin():
        await session.execute(
            update(Parked).where(Parked.id == parent[0]).values(size=3)
        )
    assert await Parked.by(Parked.key == key).run(Parked.split) == 1
    assert await step_row(Parked, parent) == "ok"
    row = await Parked.by(Parked.key == key).get()
    assert row is not None
    assert row.children_left == 1

    # A piece of the first fan-out finishing is not the new piece finishing.
    assert await step_row(Piece, await pk_of(Piece, f"{key}-0")) == "ok"
    row = await Parked.by(Parked.key == key).get()
    assert row is not None
    assert (row.children_left, row.wake_at) == (1, None)

    assert await step_row(Piece, await pk_of(Piece, f"{key}-2")) == "ok"
    row = await Parked.by(Parked.key == key).get()
    assert row is not None
    assert row.children_left == 0
    assert row.wake_at is not None


async def test_a_group_pays_only_for_the_rows_it_claims(session_factory):
    provider = uuid.uuid4().hex
    rt = runtime.current()
    await Budgeted(key=f"{provider}-0", provider=provider).start(Budgeted.work)
    assert len(await claim.claim(rt, Budgeted, 5)) == 1

    for index in (1, 2):
        await Budgeted(key=f"{provider}-{index}", provider=provider).start(
            Budgeted.work
        )
    # Three an hour, and the first claim used one: two are still owed.
    assert len(await claim.claim(rt, Budgeted, 5)) == 2


async def test_a_step_can_use_a_deferred_column(session_factory):
    key = uuid.uuid4().hex
    await Deferring(key=key).start(Deferring.work)
    row = await Deferring.by(Deferring.key == key).get()
    assert row is not None
    assert (
        await execute.execute(
            runtime.current(),
            Deferring,
            [row.id],
            (taken := await claim_row(Deferring, [row.id])).version,
            execute.Lease(taken.until),
        )
        == "ok"
    )

    async with session_factory() as session:
        notes = await session.scalar(
            select(Deferring.notes).where(Deferring.key == key)
        )
    assert notes == "worked"


async def test_a_fan_out_announces_its_children(session_factory):
    key = uuid.uuid4().hex
    heard: list[str] = []
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as conn:
        await conn.execute(f"LISTEN {notify.CHANNEL}")
        await Batch(key=key, size=2).start(Batch.split())

        async def listen() -> None:
            """Collect notifications until one names the child table."""
            async for notice in conn.notifies():
                heard.append(notice.payload)
                if notice.payload == "wf_test_item":
                    return

        await asyncio.wait_for(listen(), 10)
    assert "wf_test_item" in heard


async def test_a_wake_during_a_pass_is_not_lost(session_factory, monkeypatch):
    # A runtime of its own: the module's worker shares the current one, and a
    # pass of that worker clears the very wake this test is counting on.
    rt = runtime.Runtime(session_factory, asyncio.Event(), LEASE)
    passes: list[float] = []
    real_claim = runner.claim

    async def claim_and_hear(runtime_, cls, limit, steps=None):
        """Stand in for a claim of Parting during which a notification lands.

        Args:
            runtime_: The running engine.
            cls: The workflow class.
            limit: Most rows to claim.
            steps: The steps the worker may run.

        Returns:
            What the claim took: nothing, for Parting.
        """
        if cls is not Parting:
            return await real_claim(runtime_, cls, limit, steps)
        passes.append(time.monotonic())
        # A notification lands while the pass is still claiming, which, being a
        # query, gives the event loop a turn.
        runtime_.wake.set()
        await asyncio.sleep(0)
        return []

    monkeypatch.setattr(runner, "claim", claim_and_hear)
    worker = runner.Runner(
        rt, [Parting], 8, datetime.timedelta(seconds=30), [model.DEFAULT_LANE]
    )
    loop = asyncio.create_task(worker.loop())
    try:
        await wait_until(lambda: len(passes) >= 3, timeout=5)
    finally:
        await stop_workers([worker], [loop])


@pytest.mark.parametrize(
    "settings",
    [
        {"max_concurrency": 0},
        {"lease": datetime.timedelta(0)},
        {"poll_interval": datetime.timedelta(0)},
    ],
)
async def test_run_workflows_refuses_settings_that_cannot_work(
    session_factory, settings: dict[str, object]
):
    with pytest.raises(ValueError, match="must be"):
        async with run_workflows(session_factory, workflows=[Parting], **settings):  # pyright: ignore[reportArgumentType]
            pass


async def test_a_worker_with_a_single_connection_still_runs(session_factory):
    engine = create_async_engine(ASYNC_URL, pool_size=1, max_overflow=0)
    key = uuid.uuid4().hex
    try:
        async with run_workflows(
            async_sessionmaker(engine, expire_on_commit=False),
            workflows=[Parting],
            poll_interval=datetime.timedelta(milliseconds=100),
            lease=LEASE,
        ):
            await Parting(key=key).start(Parting.work)

            async def done() -> bool:
                """Tell whether the run has finished.

                Returns:
                    Whether it has.
                """
                row = await Parting.by(Parting.key == key).get()
                return row is not None and row.status == "done"

            await wait_until(done, timeout=15)
    finally:
        await engine.dispose()


async def test_a_claim_that_never_returns_does_not_hold_up_shutdown(
    session_factory, monkeypatch
):
    await Parting(key=f"stuck-{uuid.uuid4().hex}").start(Parting.work)
    claiming, never = asyncio.Event(), asyncio.Event()
    real_claim = runner.claim

    async def stuck_claim(runtime_, cls, limit, steps=None):
        """Stand in for a claim of Parting against a database that stopped answering.

        Args:
            runtime_: The running engine.
            cls: The workflow class.
            limit: Most rows to claim.
            steps: The steps the worker may run.

        Returns:
            What the claim took; for Parting it never returns.
        """
        if cls is not Parting:
            return await real_claim(runtime_, cls, limit, steps)
        # A database that has stopped answering.
        claiming.set()
        await never.wait()
        return []

    monkeypatch.setattr(runner, "claim", stuck_claim)
    worker = run_workflows(
        session_factory,
        workflows=[Parting],
        poll_interval=datetime.timedelta(milliseconds=50),
        lease=LEASE,
        shutdown_timeout=datetime.timedelta(milliseconds=500),
    )
    await worker.__aenter__()
    try:
        await asyncio.wait_for(claiming.wait(), 10)
    finally:
        started = time.monotonic()
        await asyncio.wait_for(worker.__aexit__(None, None, None), 10)
    assert time.monotonic() - started < 2


async def test_a_finished_run_takes_an_event_only_when_asked_to_restart(
    session_factory,
):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit(arm=False))
    pk = await pk_of(RaceReview, key)
    assert await step_row(RaceReview, pk) == "ok"
    handle = RaceReview.by(RaceReview.key == key)

    assert await handle.deliver(RaceReview.decide("approve")) == 0
    assert await handle.deliver(RaceReview.decide("approve"), restart=True) == 1
    assert await step_row(RaceReview, pk) == "ok"
    row = await handle.get()
    assert row is not None
    assert row.status == "decided:approve:manager"


async def test_a_child_that_does_not_name_its_fan_out_counts_toward_none(
    session_factory,
):
    key = uuid.uuid4().hex
    await Parked(key=key, size=1).start(Parked.split)
    parent = await pk_of(Parked, key)
    assert await step_row(Parked, parent) == "ok"
    # A child pointing at its parent the way children did before they named the
    # fan-out they belong to.
    async with session_factory() as session, session.begin():
        await session.execute(
            update(Piece)
            .where(Piece.key == f"{key}-0")
            .values(parent=Piece.parent.op("-")(literal("fan_out", String)))
        )

    # It finishes without failing, and without counting toward a join it can no
    # longer tell apart from a later one.
    assert await step_row(Piece, await pk_of(Piece, f"{key}-0")) == "ok"
    row = await Parked.by(Parked.key == key).get()
    assert row is not None
    assert (row.children_left, row.wake_at) == (1, None)


async def test_a_commit_that_cannot_land_counts_as_the_attempt_failing(
    session_factory,
):
    key = uuid.uuid4().hex
    await Cramped(key=key).start(Cramped.work)

    async def gave_up() -> bool:
        """Tell whether the run has stopped trying.

        Returns:
            Whether it has.
        """
        row = await Cramped.by(Cramped.key == key).get()
        return row is not None and row.next_step is None and row.last_error is not None

    await wait_until(gave_up)
    row = await Cramped.by(Cramped.key == key).get()
    assert row is not None
    # Counted, so the step's own retry limit applies to it: without that the row
    # keeps its schedule and runs the body again after every lease, for good.
    assert EVENTS.count(f"cramped:{key}") == 2
    assert row.attempts == 2
    assert "DataError" in (row.last_error or "")
    # The commit was rolled back, so none of the step's own work was kept.
    assert row.label == ""
    assert [(a.attempt, a.outcome) for a in await row.history()] == [
        (2, "failed"),
        (1, "retry"),
    ]


async def test_a_second_event_cannot_take_a_wait_that_already_holds_one(
    session_factory,
):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit())
    held = RaceReview.by(RaceReview.key == key)
    # The first arrives before the wait is armed, so it is held for it.
    assert await held.deliver(RaceReview.decide("approve"), key="first") == 1
    pk = await arm_wait(key)

    # The wait has its answer: a second decision neither overwrites the first
    # nor fences the step that is about to run it.
    assert await held.deliver(RaceReview.decide("reject"), key="second") == 0

    row = await RaceReview.by(RaceReview.key == key).get()
    assert row is not None
    # Due now rather than at its timeout, so it is not left behind every run
    # with a nearer deadline while it already has what it was waiting for.
    assert row.wake_at is not None
    assert row.wake_at < datetime.datetime.now(datetime.UTC) + LEASE

    assert await step_row(RaceReview, pk) == "ok"
    assert await status_is(RaceReview, key, "decided:approve:manager")()
    assert EVENTS.count(f"decide:{key}") == 1


async def test_an_event_delivered_while_the_held_one_runs_is_held_for_the_next_wait(
    session_factory, monkeypatch
):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit())
    handle = RaceReview.by(RaceReview.key == key)
    # Held before the wait is armed, then taken as the wait arms.
    assert await handle.deliver(RaceReview.decide("again"), key="first") == 1
    pk = await arm_wait(key)

    decide = RaceReview.decide.fn
    accepted: list[int] = []

    async def deciding(self, decision: str, *, by: str = "manager"):
        if self.key == key and decision == "again":
            # The held answer is being run, and it waits again: this one is for
            # that next wait, and refusing it would lose it.
            accepted.append(
                await handle.deliver(RaceReview.decide("approve"), key="second")
            )
        return await decide(self, decision, by=by)

    monkeypatch.setattr(RaceReview.decide, "fn", deciding)
    assert await step_row(RaceReview, pk) == "ok"
    assert accepted == [1]
    assert await step_row(RaceReview, pk) == "ok"
    assert await status_is(RaceReview, key, "decided:approve:manager")()
    # Each was taken once, and both are remembered.
    row = await handle.get()
    assert row is not None
    assert row.recent_event_keys == ["second", "first"]
    assert await handle.deliver(RaceReview.decide("reject"), key="second") == 0


async def test_an_event_taken_but_moved_past_before_it_ran_can_be_sent_again(
    session_factory,
):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit())
    handle = RaceReview.by(RaceReview.key == key)
    assert await handle.deliver(RaceReview.decide("approve"), key="first") == 1
    pk = await arm_wait(key)

    # A worker takes the held event to run it.
    taken = await claim_row(RaceReview, pk)
    # While its step has yet to commit, a resend is a repeat, and refused.
    assert await handle.deliver(RaceReview.decide("approve"), key="first") == 0

    # The run is sent back to the start before that step runs, so the event
    # never ran: its sender has to be able to send it again.
    assert await handle.run(RaceReview.submit()) == 1
    assert (
        await execute.execute(
            runtime.current(), RaceReview, pk, taken.version, execute.Lease(taken.until)
        )
        == "stale"
    )
    assert await step_row(RaceReview, pk) == "ok"
    assert await handle.deliver(RaceReview.decide("approve"), key="first") == 1
    assert await step_row(RaceReview, pk) == "ok"
    assert await status_is(RaceReview, key, "decided:approve:manager")()
    assert EVENTS.count(f"decide:{key}") == 1


async def test_a_child_run_again_does_not_release_its_parent_while_siblings_work(
    session_factory,
):
    key = uuid.uuid4().hex
    await Joined(key=key).start(Joined.split)
    parent_pk = await pk_of(Joined, key)
    assert await step_row(Joined, parent_pk) == "ok"

    leaf_pk = await pk_of(Leaf, f"{key}-0")
    assert await step_row(Leaf, leaf_pk) == "ok"
    parent = await Joined.by(Joined.key == key).get()
    assert parent is not None
    assert parent.children_left == 2

    # The operator runs the finished child again while its siblings are still
    # going, and it counts for nothing the second time.
    assert await Leaf.by(Leaf.key == f"{key}-0").run(Leaf.work) == 1
    assert await step_row(Leaf, leaf_pk) == "ok"

    parent = await Joined.by(Joined.key == key).get()
    assert parent is not None
    assert parent.children_left == 2
    assert EVENTS.count(f"joined-report:{key}") == 0
    assert EVENTS.count(f"leaf:{key}-0") == 2


async def test_run_leaves_a_step_already_in_flight_its_lease(session_factory):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit())
    pk = await pk_of(RaceReview, key)
    await claim_row(RaceReview, pk)

    assert await RaceReview.by(RaceReview.key == key).run(RaceReview.expire()) == 1
    row = await RaceReview.by(RaceReview.key == key).get()
    # The lease stays, so the step asked for here runs once the one in flight is
    # done rather than beside it.
    assert row is not None
    assert row.claimed_until is not None


async def test_start_gives_the_row_the_key_the_database_made(session_factory):
    key = uuid.uuid4().hex
    row = Chain(key=key)
    assert row.id is None

    assert await row.start(Chain.first) is True

    # The caller can address the run it just started without a key of its own.
    assert row.id is not None
    found = await Chain.by(Chain.id == row.id).get()
    assert found is not None
    assert found.key == key


async def test_a_customer_at_its_limit_does_not_hide_another_customers_work(
    session_factory,
):
    now = datetime.datetime.now(datetime.UTC)
    async with session_factory() as session, session.begin():
        for index in range(claim.GROUPS_PER_PASS):
            # A customer running all it may, with more waiting behind it, and
            # waiting longer than every customer after it.
            await session.execute(
                insert(Crowded).values(
                    key=f"busy-{index}-{now}",
                    customer=f"busy-{index}-{now}",
                    next_step="work",
                    wake_at=now - datetime.timedelta(minutes=10),
                    claimed_until=now + datetime.timedelta(minutes=5),
                    attempts=0,
                    wf_version=0,
                )
            )
            await session.execute(
                insert(Crowded).values(
                    key=f"busy-{index}-{now}-waiting",
                    customer=f"busy-{index}-{now}",
                    next_step="work",
                    wake_at=now - datetime.timedelta(minutes=9),
                    attempts=0,
                    wf_version=0,
                )
            )
        await session.execute(
            insert(Crowded).values(
                key=f"free-{now}",
                customer=f"free-{now}",
                next_step="work",
                wake_at=now - datetime.timedelta(minutes=1),
                attempts=0,
                wf_version=0,
            )
        )

    # One free slot, and the customers a pass looks at first can use none of it.
    claimed = await claim.claim(runtime.current(), Crowded, 1)
    assert len(claimed) == 1
    [taken] = claimed
    pk = taken.pk
    row = await Crowded.by(Crowded.id == pk[0]).get()
    assert row is not None
    assert row.customer == f"free-{now}"


async def test_a_claim_moved_on_before_it_ran_gives_its_lease_back(session_factory):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit())
    pk = await pk_of(RaceReview, key)
    taken = await claim_row(RaceReview, pk)

    # Preempted after the claim and before the step it claimed was even loaded.
    assert await RaceReview.by(RaceReview.key == key).run(RaceReview.expire()) == 1
    assert (
        await execute.execute(
            runtime.current(), RaceReview, pk, taken.version, execute.Lease(taken.until)
        )
        == "stale"
    )

    row = await RaceReview.by(RaceReview.key == key).get()
    assert row is not None
    # No step ever ran under that claim, so the step asked for instead is
    # claimable now rather than once a lease nothing used runs out.
    assert row.claimed_until is None


async def test_a_group_of_rows_with_no_group_is_held_to_its_limit_too(session_factory):
    now = datetime.datetime.now(datetime.UTC)
    spec = Crowded.__workflow_limit__
    assert spec is not None
    async with session_factory() as session, session.begin():
        # The rows with no customer are one group, and it runs all it may.
        await session.execute(
            insert(Crowded).values(
                key=f"none-running-{now}",
                customer=None,
                next_step="work",
                wake_at=now - datetime.timedelta(minutes=10),
                claimed_until=now + datetime.timedelta(minutes=5),
                attempts=0,
                wf_version=0,
            )
        )
        await session.execute(
            insert(Crowded).values(
                key=f"none-waiting-{now}",
                customer=None,
                next_step="work",
                wake_at=now - datetime.timedelta(minutes=9),
                attempts=0,
                wf_version=0,
            )
        )

    groups = await claim.waiting_groups(
        runtime.current(), Crowded, spec, Crowded.customer, 10, None
    )
    # Equality matches no NULL, so without a null-safe comparison this group
    # looks idle and takes a place a group that could run should have.
    assert None not in groups


async def stopped_mid_step(*keys: str) -> runner.Runner:
    """Run a lingering step per key, then stop the worker while it is still in them.

    Args:
        *keys: The rows' keys.

    Returns:
        The stopped worker, with its steps still to be drained.
    """
    LINGERING.clear()
    # The rows an earlier test left behind are claimable again, and would take
    # the slots this one is watching; park them so the worker sees only these.
    async with runtime.current().session_factory() as session, session.begin():
        await session.execute(
            update(Lingering)
            .values(next_step=None, wake_at=None)
            .execution_options(synchronize_session=False)
        )
    for key in keys:
        await Lingering(key=key).start(Lingering.work)
    worker = runner.Runner(
        runtime.current(), [Lingering], len(keys), datetime.timedelta(milliseconds=50)
    )
    loop = asyncio.create_task(worker.loop())
    await wait_until(lambda: all(f"lingering:{key}" in EVENTS for key in keys))
    worker.stop()
    await loop
    return worker


async def test_a_step_cancelled_on_the_way_out_gives_its_row_back(session_factory):
    key = uuid.uuid4().hex
    worker = await stopped_mid_step(key)

    # The deploy lands mid-step: what is still running is cancelled.
    await worker.drain(datetime.timedelta(milliseconds=100))

    row = await Lingering.by(Lingering.key == key).get()
    assert row is not None
    # Free for the next worker at once, rather than after a lease nobody holds.
    assert row.claimed_until is None
    assert row.next_step == "work"


async def test_a_lease_taken_over_by_another_worker_is_not_given_back(session_factory):
    key = uuid.uuid4().hex
    worker = await stopped_mid_step(key)

    # Another worker takes the row over while this one is still shutting down.
    theirs = await claim_row(Lingering, await pk_of(Lingering, key))
    await worker.drain(datetime.timedelta(milliseconds=100))

    row = await Lingering.by(Lingering.key == key).get()
    assert row is not None
    # Only the lease this worker wrote was ever its to give back.
    assert row.claimed_until == theirs.until


async def test_a_preempted_claim_gives_its_lease_back_on_a_pool_of_one(
    session_factory,
):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit())
    pk = await pk_of(RaceReview, key)
    taken = await claim_row(RaceReview, pk)
    assert await RaceReview.by(RaceReview.key == key).run(RaceReview.expire()) == 1

    # A pool that can only ever hand out one connection, which is what giving
    # the lease back while still holding the one that read the row waits for.
    narrow = create_async_engine(ASYNC_URL, pool_size=1, max_overflow=0, pool_timeout=5)
    try:
        outcome = await asyncio.wait_for(
            execute.execute(
                runtime.Runtime(
                    async_sessionmaker(narrow, expire_on_commit=False),
                    asyncio.Event(),
                    LEASE,
                ),
                RaceReview,
                pk,
                taken.version,
                execute.Lease(taken.until),
            ),
            timeout=15,
        )
    finally:
        await narrow.dispose()

    assert outcome == "stale"
    row = await RaceReview.by(RaceReview.key == key).get()
    assert row is not None
    assert row.claimed_until is None


async def test_giving_rows_back_holds_shutdown_up_by_the_same_bound_either_way(
    session_factory, monkeypatch
):
    keys = [uuid.uuid4().hex for _ in range(5)]
    worker = await stopped_mid_step(*keys)

    async def never(*args, **kwargs) -> None:
        """Stand in for a database that has stopped answering."""
        await asyncio.sleep(3600)

    budget = datetime.timedelta(milliseconds=200)
    monkeypatch.setattr(runner, "release", never)
    monkeypatch.setattr(runner, "GIVE_BACK", budget)

    started = time.monotonic()
    await worker.drain(datetime.timedelta(milliseconds=50))
    took = time.monotonic() - started

    # One budget for all five, not one each: the rows left over wait out
    # their leases rather than holding shutdown open a row at a time.
    assert took < (budget * 3).total_seconds()


async def test_a_row_the_database_refuses_does_not_strand_the_others(
    session_factory, monkeypatch
):
    keys = [uuid.uuid4().hex for _ in range(3)]
    worker = await stopped_mid_step(*keys)
    real = runner.release
    refused: list[str] = []

    async def refuse_the_first(runtime_, cls, pk, held):
        """Fail the first lease handed back, and give the rest back for real.

        Args:
            runtime_: The running engine.
            cls: The workflow class.
            pk: The row's primary key values.
            held: The lease the step held.

        Raises:
            RuntimeError: For the first row, standing in for a refused write.
        """
        refused.append("x")
        if len(refused) == 1:
            msg = "the database would not take it back"
            raise RuntimeError(msg)
        await real(runtime_, cls, pk, held)

    monkeypatch.setattr(runner, "release", refuse_the_first)
    await worker.drain(datetime.timedelta(milliseconds=50))

    rows_back = await Lingering.by(Lingering.key.in_(keys)).all()
    # Every row was tried, and the two that could be given back were.
    assert len(refused) == 3
    assert sum(row.claimed_until is None for row in rows_back) == 2


async def test_cancel_stops_a_run_where_it_stands(session_factory):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit())
    held = RaceReview.by(RaceReview.key == key)
    # Delivered before the wait arms, so the run is holding it when it arms.
    assert await held.deliver(RaceReview.decide("approve"), key="late") == 1
    await arm_wait(key)
    parked = await held.get()
    assert parked is not None
    assert parked.pending_event is not None

    assert await held.cancel() == 1

    row = await held.get()
    assert row is not None
    # Nothing scheduled, nothing waited for, and the event it was holding gone.
    assert (row.next_step, row.waiting_for, row.pending_event) == (None, None, None)
    assert row.claimed_until is None
    # Already cancelled, so there is nothing left to cancel.
    assert await held.cancel() == 0


async def test_a_cancelled_child_lets_its_parent_carry_on(session_factory):
    key = uuid.uuid4().hex
    await Joined(key=key).start(Joined.split)
    parent_pk = await pk_of(Joined, key)
    assert await step_row(Joined, parent_pk) == "ok"

    # One leaf is cancelled outright; the other two finish normally.
    assert await Leaf.by(Leaf.key == f"{key}-0").cancel() == 1
    for index in (1, 2):
        assert await step_row(Leaf, await pk_of(Leaf, f"{key}-{index}")) == "ok"

    parent = await Joined.by(Joined.key == key).get()
    assert parent is not None
    # Counted as finished, as one that gave up is, so the join is not stranded.
    assert parent.children_left == 0
    assert await step_row(Joined, parent_pk) == "ok"
    assert EVENTS.count(f"joined-report:{key}") == 1


async def test_an_idle_worker_waits_for_the_run_that_is_due_soonest(session_factory):
    rt = runtime.current()
    only: dict[type[Workflow], list[str] | None] = {Resting: None}
    # Nothing scheduled at all: there is no time to wait for.
    assert await claim.next_due(rt, [Resting], only) is None

    later, now_key = uuid.uuid4().hex, uuid.uuid4().hex
    async with session_factory() as session, session.begin():
        await session.execute(
            insert(Resting).values(
                key=later,
                next_step="rest",
                wake_at=func.now() + datetime.timedelta(hours=3),
                attempts=0,
                wf_version=0,
            )
        )
    away = await claim.next_due(rt, [Resting], only)
    assert away is not None
    # Waiting for it, rather than asking again every poll interval.
    assert datetime.timedelta(hours=2) < away.away < datetime.timedelta(hours=4)

    await Resting(key=now_key).start(Resting.rest())
    due = await claim.next_due(rt, [Resting], only)
    assert due is not None
    # Something is due already, so an idle worker does not wait at all.
    assert due.away <= datetime.timedelta()

    await Resting.by(Resting.key.in_([later, now_key])).cancel()
    assert await claim.next_due(rt, [Resting], only) is None


async def test_a_run_waiting_on_an_event_is_not_something_to_wait_for(
    session_factory,
):
    rt = runtime.current()
    only: dict[type[Workflow], list[str] | None] = {Resting: None}
    await Resting.by().cancel()
    assert await claim.next_due(rt, [Resting], only) is None

    async with session_factory() as session, session.begin():
        # Parked on a wait with no deadline, as a run that deferred its answer
        # is: only an event moves it, and an event announces itself.
        await session.execute(
            insert(Resting).values(
                key=uuid.uuid4().hex,
                waiting_for="rest",
                next_step=None,
                wake_at=None,
                attempts=0,
                wf_version=0,
            )
        )

    try:
        # No time here for an idle worker to sit waiting for.
        assert await claim.next_due(rt, [Resting], only) is None
    finally:
        await Resting.by().cancel()


async def test_a_lease_running_out_is_what_an_idle_worker_waits_for(session_factory):
    rt = runtime.current()
    only: dict[type[Workflow], list[str] | None] = {Resting: None}
    await Resting.by().cancel()
    assert await claim.next_due(rt, [Resting], only) is None

    async with session_factory() as session, session.begin():
        # Claimed by a worker that may be gone, and long overdue by its own
        # wake_at: the lease is when to find out, not the wake_at underneath it.
        await session.execute(
            insert(Resting).values(
                key=uuid.uuid4().hex,
                next_step="rest",
                wake_at=func.now() - datetime.timedelta(hours=1),
                claimed_until=func.now() + datetime.timedelta(hours=3),
                attempts=0,
                wf_version=0,
            )
        )

    try:
        away = await claim.next_due(rt, [Resting], only)
        assert away is not None
        # Waiting for the lease rather than asking after a row it cannot take.
        assert datetime.timedelta(hours=2) < away.away < datetime.timedelta(hours=4)
    finally:
        await Resting.by().cancel()


async def test_the_instant_a_worker_waits_for_is_the_databases_own(session_factory):
    rt = runtime.current()
    only: dict[type[Workflow], list[str] | None] = {Resting: None}
    await Resting.by().cancel()
    assert await claim.next_due(rt, [Resting], only) is None

    key = uuid.uuid4().hex
    async with session_factory() as session, session.begin():
        await session.execute(
            insert(Resting).values(
                key=key,
                next_step="rest",
                wake_at=func.now() + datetime.timedelta(hours=3),
                attempts=0,
                wf_version=0,
            )
        )
    try:
        first = await claim.next_due(rt, [Resting], only)
        second = await claim.next_due(rt, [Resting], only)
        assert first is not None
        assert second is not None
        # The same answer asked twice is the same instant, which is what lets a
        # caller registering it elsewhere write once rather than once a pass.
        assert first.at == second.at
        async with session_factory() as session:
            stored = (
                await session.execute(select(Resting.wake_at).where(Resting.key == key))
            ).scalar_one()
        assert first.at == stored
        # And the wait still agrees with it.
        assert datetime.timedelta(hours=2) < first.away < datetime.timedelta(hours=4)
    finally:
        await Resting.by().cancel()


async def test_a_worker_reports_the_instant_it_waits_for_when_it_changes(
    session_factory,
):
    reported: list[datetime.datetime | None] = []

    async def note(at):
        """Record what the worker says it is waiting for.

        Args:
            at: The instant, or None.
        """
        reported.append(at)
        await asyncio.sleep(0)

    await Resting.by().cancel()
    # Idling as fast as it polls, so the window below holds several passes: a
    # worker that reported every pass rather than every change would show up.
    worker = runner.Runner(
        runtime.current(),
        [Resting],
        4,
        datetime.timedelta(milliseconds=50),
        max_idle_interval=datetime.timedelta(milliseconds=50),
        on_idle=note,
    )
    loop = asyncio.create_task(worker.loop())
    try:
        await wait_until(lambda: len(reported) >= 1)
        # Nothing scheduled is an answer, and asking again is not a new one.
        assert reported == [None]
        await asyncio.sleep(0.3)
        assert reported == [None]

        key = uuid.uuid4().hex
        async with session_factory() as session, session.begin():
            await session.execute(
                insert(Resting).values(
                    key=key,
                    next_step="rest",
                    wake_at=func.now() + datetime.timedelta(hours=3),
                    attempts=0,
                    wf_version=0,
                )
            )
        await wait_until(lambda: len(reported) >= 2)
        assert reported[1] is not None
        async with session_factory() as session:
            stored = (
                await session.execute(select(Resting.wake_at).where(Resting.key == key))
            ).scalar_one()
        assert reported[1] == stored
        # Still the same answer, so still nothing to say.
        await asyncio.sleep(0.3)
        assert len(reported) == 2
    finally:
        worker.stop()
        loop.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await loop
        await Resting.by().cancel()


async def test_a_broken_on_idle_does_not_stop_the_worker(session_factory):
    calls = []

    async def broken(at):
        """Fail the way an application's own registration might.

        Args:
            at: The instant, or None.

        Raises:
            RuntimeError: Always.
        """
        calls.append(at)
        await asyncio.sleep(0)
        msg = "the platform said no"
        raise RuntimeError(msg)

    await Resting.by().cancel()
    worker = runner.Runner(
        runtime.current(),
        [Resting],
        4,
        datetime.timedelta(milliseconds=50),
        on_idle=broken,
    )
    loop = asyncio.create_task(worker.loop())
    try:
        await wait_until(lambda: len(calls) >= 1)
        # Whatever the application does there is its own business; a worker
        # that stopped claiming over it would be the worse failure.
        key = uuid.uuid4().hex
        await Resting(key=key).start(Resting.rest())

        async def ran() -> bool:
            async with session_factory() as session:
                return (
                    await session.execute(
                        select(Resting.next_step).where(Resting.key == key)
                    )
                ).scalar_one() is None

        await wait_until(ran)
        assert len(calls) >= 1
    finally:
        worker.stop()
        loop.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await loop


@contextlib.asynccontextmanager
async def only_worker(
    session_factory: async_sessionmaker[AsyncSession],
    on_idle: runner.OnIdle | None = None,
) -> AsyncIterator[runner.Runner]:
    """Run a worker over Resting alone, as the only engine in this process.

    Its own runtime, because the counter ``wake`` waits on belongs to the
    runtime rather than the worker: the module's own worker shares the one this
    would otherwise use, and its idle passes would settle a wait meant for this
    one.

    Args:
        session_factory: The database to work against.
        on_idle: Told what the worker is waiting for, if anything wants to know.

    Yields:
        The running worker.
    """
    mine = runtime.Runtime(session_factory, asyncio.Event(), LEASE)
    previous = runtime.replace_current(mine)
    worker = runner.Runner(mine, [Resting], 4, MINUTE, on_idle=on_idle)
    loop = asyncio.create_task(worker.loop())
    try:
        yield worker
    finally:
        worker.stop()
        loop.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await loop
        runtime.replace_current(previous)


async def test_wake_settles_once_the_worker_has_nothing_left_to_take(
    session_factory,
):
    await Resting.by().cancel()
    key = uuid.uuid4().hex
    # Written straight into the table, so nothing announces it, and the poll is
    # a minute away: only the wake gets the worker to look.
    async with session_factory() as session, session.begin():
        await session.execute(
            insert(Resting).values(
                key=key,
                next_step="rest",
                wake_at=func.now(),
                attempts=0,
                wf_version=0,
            )
        )

    async with only_worker(session_factory):
        assert await runner.wake(datetime.timedelta(seconds=30))
        async with session_factory() as session:
            left = (
                await session.execute(
                    select(Resting.next_step).where(Resting.key == key)
                )
            ).scalar_one()
    # Settled means a pass that took nothing, which this worker could only make
    # once it had run what was due.
    assert left is None


async def test_wake_waits_for_the_steps_it_took_to_finish(session_factory, monkeypatch):
    await Resting.by().cancel()
    key = uuid.uuid4().hex
    async with session_factory() as session, session.begin():
        await session.execute(
            insert(Resting).values(
                key=key,
                next_step="rest",
                wake_at=func.now(),
                attempts=0,
                wf_version=0,
            )
        )
    running = asyncio.Event()
    release = asyncio.Event()
    real = runner.execute

    async def held(*args, **kwargs):
        """Run the step only once the test lets it, the way a slow one would.

        Args:
            *args: Passed on to execute.
            **kwargs: Passed on to execute.

        Returns:
            What execute returns.
        """
        running.set()
        await release.wait()
        return await real(*args, **kwargs)

    asked = asyncio.Event()
    ask = runner.Runner.until_something_is_due

    async def told(self: runner.Runner) -> float:
        """Ask as the worker would, then say a pass that took nothing got here.

        Args:
            self: The worker.

        Returns:
            Seconds to wait.
        """
        seconds = await ask(self)
        asked.set()
        return seconds

    monkeypatch.setattr(runner, "execute", held)
    monkeypatch.setattr(runner.Runner, "until_something_is_due", told)
    async with only_worker(session_factory) as worker:
        passes = worker.runtime.settled.passes
        waiting = asyncio.create_task(runner.wake(datetime.timedelta(seconds=30)))
        await asyncio.wait_for(running.wait(), 10)
        # The pass after the claim takes nothing, the run being leased, but the
        # step is still running: a host suspending now would stop it midway.
        # Counting that pass happens before the worker next yields, so it has
        # been decided by the time this resumes.
        await asyncio.wait_for(asked.wait(), 10)
        assert worker.runtime.settled.passes == passes
        assert not waiting.done()
        release.set()
        assert await waiting
        async with session_factory() as session:
            left = (
                await session.execute(
                    select(Resting.next_step).where(Resting.key == key)
                )
            ).scalar_one()
    assert left is None


async def test_wake_waits_for_what_the_last_step_left_due(session_factory, monkeypatch):
    await Resting.by().cancel()
    key = uuid.uuid4().hex
    async with session_factory() as session, session.begin():
        await session.execute(
            insert(Resting).values(
                key=key,
                next_step="hop",
                wake_at=func.now(),
                attempts=0,
                wf_version=0,
            )
        )
    ask = runner.Runner.until_something_is_due

    async def late(self: runner.Runner) -> float:
        """Let the steps in flight finish while the worker is asking.

        Args:
            self: The worker.

        Returns:
            Seconds to wait.
        """
        if self.inflight:
            await asyncio.wait(set(self.inflight))
        return await ask(self)

    monkeypatch.setattr(runner.Runner, "until_something_is_due", late)
    async with only_worker(session_factory):
        assert await runner.wake(datetime.timedelta(seconds=30))
        async with session_factory() as session:
            left = (
                await session.execute(
                    select(Resting.next_step).where(Resting.key == key)
                )
            ).scalar_one()
    # The hop left its rest due now, and nothing is in flight once it is done,
    # but the pass that saw that was asked before the rest existed.
    assert left is None


async def test_wake_waits_for_the_next_wake_up_to_have_been_registered(
    session_factory,
):
    await Resting.by().cancel()
    started = 0
    finished = 0
    first = asyncio.Event()

    async def slow_register(_at):
        """Take a while over it, the way a call to a platform would.

        Args:
            _at: The instant the worker is waiting for.
        """
        nonlocal started, finished
        started += 1
        first.set()
        await asyncio.sleep(0.3)
        finished += 1

    async with only_worker(session_factory, on_idle=slow_register):
        # Let it settle on having nothing, so the registration below is the one
        # this wake is waiting for rather than one already done.
        await asyncio.wait_for(first.wait(), 10)
        await wait_until(lambda: finished == 1)

        async with session_factory() as session, session.begin():
            await session.execute(
                insert(Resting).values(
                    key=uuid.uuid4().hex,
                    next_step="rest",
                    wake_at=func.now() + datetime.timedelta(hours=3),
                    attempts=0,
                    wf_version=0,
                )
            )
        try:
            assert await runner.wake(datetime.timedelta(seconds=30))
            # The caller lets the machine stop when this returns, so it must not
            # return while the registration for that new instant is still in
            # flight: the platform would be holding the old answer, or none.
            assert (started, finished) == (2, 2)
        finally:
            await Resting.by().cancel()


async def test_a_wake_up_that_could_not_be_registered_is_tried_again(
    session_factory,
):
    await Resting.by().cancel()
    attempts: list[datetime.datetime | None] = []
    refusing = True

    async def flaky(at):
        """Refuse once, the way a platform having a moment would.

        Args:
            at: The instant the worker is waiting for.

        Raises:
            RuntimeError: While the platform is refusing.
        """
        attempts.append(at)
        await asyncio.sleep(0)
        if refusing:
            msg = "the platform said no"
            raise RuntimeError(msg)

    async with only_worker(session_factory, on_idle=flaky):
        await wait_until(lambda: len(attempts) >= 1)
        first = attempts[0]
        refusing = False
        # Round again; its next pass is otherwise a poll interval away.
        runtime.current().wake.set()
        # The same answer, but it was never taken: a worker that remembered
        # having said it would leave the platform with nothing registered.
        await wait_until(lambda: len(attempts) >= 2)
        assert attempts[1] == first


async def test_waiting_for_a_pass_gives_up_rather_than_hanging():
    # What wake() reports false on: a worker that is gone, or too busy to make
    # a pass inside the caller's timeout. The caller is holding a request open
    # on the answer, so it has to come back either way.
    settled = runtime.Settled()
    assert not await settled.after(settled.passes, datetime.timedelta(milliseconds=100))

    await settled.record()
    # And a pass that did happen is not missed.
    assert await settled.after(settled.passes - 1, datetime.timedelta(seconds=5))


async def test_wake_tells_the_callers_past_the_cap_to_get_on_with_it(
    session_factory, monkeypatch
):
    # A worker of this test's own, like the other wake tests: the count below is
    # set rather than raced up to with a crowd of tasks, since what is worth
    # pinning is what a caller past the cap is told and not how quickly asyncio
    # schedules coroutines.
    async with only_worker(session_factory):
        rt = runtime.current()
        rt.wake.clear()
        monkeypatch.setattr(runner, "_waiting", runner.WAITERS)

        # Not queued behind callers asking for the same thing, and not told the
        # worker caught up either: it watched nothing, and a caller that let the
        # machine stop on that would strand the work.
        assert await runner.wake(datetime.timedelta(seconds=10)) is False
        # Returned without joining the wait, which is the point of the cap.
        assert runner._waiting == runner.WAITERS
        # Still asked the worker to look, which is the half it can honestly do.
        assert rt.wake.is_set()

        # Under the cap the same call waits for a pass and gets one, so the
        # false above is the cap talking rather than anything else.
        monkeypatch.setattr(runner, "_waiting", 0)
        assert await runner.wake(datetime.timedelta(seconds=30)) is True


async def test_a_table_that_cannot_be_asked_does_not_decide_the_wait(session_factory):
    class Absent(Base, Workflow):
        """A workflow whose table was never created."""

        __tablename__ = "wf_test_absent"

        id: Mapped[int] = mapped_column(primary_key=True)

        @step
        async def work(self):
            """Never runs; the table is not there."""

    rt = runtime.current()
    asked: dict[type[Workflow], list[str] | None] = {Absent: None, Resting: None}
    key = uuid.uuid4().hex
    await Resting(key=key).start(Resting.rest())
    try:
        # The table that answers still decides the wait, rather than the one
        # that cannot be read leaving the worker to sit out its whole cap.
        due = await claim.next_due(rt, [Absent, Resting], asked)
        assert due is not None
        assert due.away <= datetime.timedelta()
    finally:
        await Resting.by(Resting.key == key).cancel()
        REGISTRY.pop(Absent.__tablename__, None)


async def test_a_database_that_answers_nothing_is_not_nothing_being_due(
    session_factory,
):
    class Missing(Base, Workflow):
        """A workflow whose table was never created."""

        __tablename__ = "wf_test_missing"

        id: Mapped[int] = mapped_column(primary_key=True)

        @step
        async def work(self):
            """Never runs; the table is not there."""

    rt = runtime.current()
    try:
        # Every table refused, which the per-table handling would otherwise
        # report as "nothing is scheduled" -- and the worker would sleep out an
        # idle interval it was never told about.
        with pytest.raises(claim.UnansweredError):
            await claim.next_due(rt, [Missing], {Missing: None})

        # Told apart from one table of several being unreadable, which the
        # worker carries on past.
        key = uuid.uuid4().hex
        await Resting(key=key).start(Resting.rest())
        try:
            due = await claim.next_due(
                rt, [Missing, Resting], {Missing: None, Resting: None}
            )
            assert due is not None
            assert due.away <= datetime.timedelta()
        finally:
            await Resting.by(Resting.key == key).cancel()

        # And a worker with nothing readable looks again at once rather than
        # sleeping out its idle interval.
        worker = runner.Runner(
            rt,
            [Missing],
            4,
            datetime.timedelta(milliseconds=20),
            max_idle_interval=MINUTE,
        )
        assert await worker.until_something_is_due() == pytest.approx(0.02)
    finally:
        REGISTRY.pop(Missing.__tablename__, None)


async def test_cancel_leaves_a_step_already_running_its_lease(session_factory):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit())
    pk = await pk_of(RaceReview, key)
    await claim_row(RaceReview, pk)

    assert await RaceReview.by(RaceReview.key == key).cancel() == 1

    row = await RaceReview.by(RaceReview.key == key).get()
    assert row is not None
    # A run started again straight afterwards waits for the cancelled step to
    # be done rather than acting beside it.
    assert row.claimed_until is not None


async def test_a_child_that_finishes_as_it_is_cancelled_counts_once(session_factory):
    key = uuid.uuid4().hex
    await Joined(key=key).start(Joined.split)
    parent_pk = await pk_of(Joined, key)
    assert await step_row(Joined, parent_pk) == "ok"

    # The child finishes under the cancel, which is the race the lock closes:
    # counted by its own commit, it must not be counted by the cancel as well.
    assert await step_row(Leaf, await pk_of(Leaf, f"{key}-0")) == "ok"
    assert await Leaf.by(Leaf.key == f"{key}-0").cancel() == 0

    parent = await Joined.by(Joined.key == key).get()
    assert parent is not None
    assert parent.children_left == 2
    assert EVENTS.count(f"joined-report:{key}") == 0


async def test_no_run_is_cancelled_without_its_parent_being_told(session_factory):
    # Cancel reads the rows it will stop and stops them. Read and written as two
    # statements, the write took a snapshot of its own, so a run that started
    # matching in between was cancelled without having been read: nothing
    # counted it against its parent, and that parent waited for a child that
    # could no longer report.
    watched, late = uuid.uuid4().hex, uuid.uuid4().hex
    for key in (watched, late):
        await Joined(key=key).start(Joined.split)
        assert await step_row(Joined, await pk_of(Joined, key)) == "ok"
    async with session_factory() as session:
        pointer = (
            await session.execute(select(Leaf.parent).where(Leaf.key == f"{late}-0"))
        ).scalar_one()

    arriving = f"{watched}-late"
    sent = []
    bind = runtime.current().session_factory.kw["bind"]

    def arrive(conn, cursor, statement, *args):
        """Commit a matching run on another connection as the cancel runs.

        Args:
            conn: The connection.
            cursor: Its cursor.
            statement: The SQL about to be sent.
            *args: The rest of the event's arguments.
        """
        if not statement.lstrip().upper().startswith(("UPDATE", "WITH")) or sent:
            return
        sent.append(statement)
        with psycopg.connect(URL, autocommit=True) as other:
            other.execute(
                "insert into wf_test_leaf"
                " (key, status, next_step, wake_at, attempts, wf_version, parent)"
                " values (%s, 'new', 'work', now(), 0, 0, %s)",
                (arriving, json.dumps(pointer)),
            )

    sa_event.listen(bind.sync_engine, "before_cursor_execute", arrive)
    try:
        cancelled = await Leaf.by(Leaf.key.like(f"{watched}-%")).cancel()
    finally:
        sa_event.remove(bind.sync_engine, "before_cursor_execute", arrive)
    assert sent, "the cancel sent no statement to hook"

    async with session_factory() as session:
        left = (
            await session.execute(select(Leaf.next_step).where(Leaf.key == arriving))
        ).scalar_one()
        counted = (
            await session.execute(
                select(Joined.children_left).where(Joined.key == late)
            )
        ).scalar_one()
    # Whether the late run was inside the cancel or outside it, the two agree:
    # a run it stopped was counted against its parent, and one it left alone is
    # still scheduled to run and count itself.
    if left is None:
        assert cancelled == 4
        assert counted == 2
    else:
        assert (cancelled, left, counted) == (3, "work", 3)


@pytest.mark.parametrize(
    ("given", "stored"),
    [({}, "pending"), ({"note": None}, None), ({"note": "written"}, "written")],
)
async def test_start_stores_what_the_caller_set_including_none(
    session_factory, given, stored
):
    key = uuid.uuid4().hex
    # An explicit None used to read the same as never setting the column, so the
    # column default was stored over it -- unlike adding the row to a session.
    await Noted(key=key, **given).start(Noted.go)
    async with session_factory() as session:
        note = (
            await session.execute(select(Noted.note).where(Noted.key == key))
        ).scalar_one()
    assert note == stored


async def test_a_key_is_taken_when_the_run_runs_the_event_not_when_it_is_held(
    session_factory,
):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit(pause_s=0))
    handle = RaceReview.by(RaceReview.key == key)

    # Held while the first step is still to run, for the wait it will arm.
    assert await handle.deliver(RaceReview.decide("approve"), key="evt-1") == 1
    async with session_factory() as session:
        held, remembered = (
            await session.execute(
                select(RaceReview.pending_event, RaceReview.recent_event_keys).where(
                    RaceReview.key == key
                )
            )
        ).one()
    # The key travels with the event rather than being remembered now: an event
    # discarded unrun would otherwise refuse the resend that is the only way back.
    assert held["key"] == "evt-1"
    assert remembered is None
    # A resend while it is still held is still a repeat, and refused as one.
    assert await handle.deliver(RaceReview.decide("reject"), key="evt-1") == 0

    # The run arms a wait for something else, so the held event is discarded --
    # and with it the claim on that key.
    pk = await pk_of(RaceReview, key)
    async with session_factory() as session, session.begin():
        await session.execute(
            update(RaceReview)
            .where(*rows.pk_filter(RaceReview, pk))
            .values(
                waiting_for="decide",
                pending_event=None,
                next_step=None,
                # A wait with no deadline, which is what this is about: one whose
                # deadline had passed would refuse the event for that reason.
                wake_at=None,
            )
            .execution_options(synchronize_session=False)
        )

    assert await handle.deliver(RaceReview.decide("approve"), key="evt-1") == 1
    assert await step_row(RaceReview, pk) == "ok"
    assert await status_is(RaceReview, key, "decided:approve:manager")()
    # Now it has been run, so it is remembered and a resend changes nothing.
    assert (
        await handle.deliver(RaceReview.decide("reject"), key="evt-1", restart=True)
        == 0
    )


async def test_a_run_going_round_a_schedule_keeps_no_event(session_factory):
    key = uuid.uuid4().hex
    await Repeating(key=key).start(Repeating.tick("interval"))
    pk = await pk_of(Repeating, key)
    handle = Repeating.by(Repeating.key == key)

    # A run on every() always has a next step and never arms a wait, so an event
    # held on one used to stay for good: never run, and refusing every event
    # after it.
    assert await handle.deliver(Repeating.tick("cron")) == 1
    assert await step_row(Repeating, pk) == "ok"
    async with session_factory() as session:
        held = (
            await session.execute(
                select(Repeating.pending_event).where(Repeating.key == key)
            )
        ).scalar_one()
    assert held is None
    # Which is what lets the next one in.
    assert await handle.deliver(Repeating.tick("cron")) == 1


async def test_a_restart_leaves_a_cancelled_step_its_lease(session_factory):
    key = uuid.uuid4().hex
    await RaceReview(key=key).start(RaceReview.submit())
    pk = await pk_of(RaceReview, key)
    claimed = await claim_row(RaceReview, pk)
    await RaceReview.by(RaceReview.key == key).cancel()

    assert (
        await RaceReview.by(RaceReview.key == key).deliver(
            RaceReview.decide("approve"), restart=True
        )
        == 1
    )
    async with session_factory() as session:
        lease = (
            await session.execute(
                select(RaceReview.claimed_until).where(RaceReview.key == key)
            )
        ).scalar_one()
    # As ``run`` leaves it: the cancelled step is still running, and the step
    # started here waits for it rather than running beside it.
    assert lease == claimed.until


async def test_a_run_holding_its_answer_is_due_now(session_factory):
    rt = runtime.current()
    only: dict[type[Workflow], list[str] | None] = {Resting: None}
    await Resting.by().cancel()

    async with session_factory() as session, session.begin():
        # Parked on a wait, holding the answer, with no time of its own: the
        # claim takes it, so the wait must not be sat out either.
        await session.execute(
            insert(Resting).values(
                key=uuid.uuid4().hex,
                waiting_for="rest",
                pending_event={"step": "rest", "args": {}},
                next_step=None,
                wake_at=None,
                attempts=0,
                wf_version=0,
            )
        )

    try:
        due = await claim.next_due(rt, [Resting], only)
        assert due is not None
        assert due.away <= datetime.timedelta()
    finally:
        # Left behind, this row is due for every later test that asks.
        await Resting.by().cancel()


async def test_a_long_poll_interval_is_still_allowed(session_factory):
    minute = MINUTE
    # Longer than the default idle cap, which was allowed before there was one
    # and has to stay allowed; a worker never waits less than it was told to.
    worker = runner.Runner(runtime.current(), [Resting], 4, minute)
    assert worker.max_idle_interval >= minute

    engine = create_async_engine(ASYNC_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with run_workflows(factory, workflows=[Resting], poll_interval=minute):
            pass
        with pytest.raises(ValueError, match="cannot be shorter"):
            async with run_workflows(
                factory,
                workflows=[Resting],
                poll_interval=minute,
                max_idle_interval=datetime.timedelta(seconds=1),
            ):
                pass
    finally:
        await engine.dispose()


async def test_cancel_reads_its_rows_under_a_lock(session_factory):
    key = uuid.uuid4().hex
    await Joined(key=key).start(Joined.split)
    assert await step_row(Joined, await pk_of(Joined, key)) == "ok"

    statements: list[str] = []
    bind = runtime.current().session_factory.kw["bind"]

    def record(conn, cursor, statement, *args):
        """Keep every statement the cancel sends.

        Args:
            conn: The connection.
            cursor: Its cursor.
            statement: The SQL.
            *args: The rest of the event's arguments.
        """
        statements.append(statement)

    sa_event.listen(bind.sync_engine, "before_cursor_execute", record)
    try:
        assert await Leaf.by(Leaf.key == f"{key}-0").cancel() == 1
    finally:
        sa_event.remove(bind.sync_engine, "before_cursor_execute", record)

    # Picked under a lock, so a child that finishes between being read and
    # being cancelled cannot be counted by its own commit and by this one as
    # well. In the same statement as the write, so there is no moment between
    # them for a row to arrive in either.
    writes = [sql for sql in statements if "UPDATE WF_TEST_LEAF" in sql.upper()]
    assert len(writes) == 1, statements
    assert "FOR UPDATE" in writes[0].upper()


async def test_a_child_that_finishes_before_the_cancel_is_counted_once(
    session_factory,
):
    key = uuid.uuid4().hex
    await Joined(key=key).start(Joined.split)
    assert await step_row(Joined, await pk_of(Joined, key)) == "ok"
    assert await step_row(Leaf, await pk_of(Leaf, f"{key}-0")) == "ok"

    # Already finished and already counted, so there is nothing left to cancel
    # and nothing for the cancel to count again.
    assert await Leaf.by(Leaf.key == f"{key}-0").cancel() == 0

    parent = await Joined.by(Joined.key == key).get()
    assert parent is not None
    assert parent.children_left == 2
    assert EVENTS.count(f"joined-report:{key}") == 0


async def test_a_worker_that_could_not_ask_looks_again_soon(
    session_factory, monkeypatch
):
    worker = runner.Runner(
        runtime.current(),
        [Resting],
        4,
        datetime.timedelta(milliseconds=20),
        max_idle_interval=MINUTE,
    )

    async def refuse(*_args, **_kwargs):
        """Fail the way a database that is down would.

        Raises:
            RuntimeError: Always.
        """
        await asyncio.sleep(0)
        msg = "the database is not answering"
        raise RuntimeError(msg)

    monkeypatch.setattr(runner, "next_due", refuse)
    # Not knowing is not the same as knowing there is nothing: waiting out the
    # idle interval would leave a database that came back unnoticed until the
    # end of a wait it was never asked about.
    assert await worker.until_something_is_due() == pytest.approx(0.02)
    # Doubling while it keeps happening, since the other thing this looks like
    # is a table that was never migrated: asked after every poll interval for
    # the life of the process, and logged each time.
    # Far more refusals than it takes to reach the cap: the wait is doubled
    # rather than recomputed from how many there have been, so nothing here
    # raises two to the power of how long a database has been down -- which
    # overflows a timedelta, out of a loop with nothing to catch it, and the
    # worker would stop claiming for good on a database that later came back.
    waits = [await worker.until_something_is_due() for _ in range(200)]
    assert waits[:5] == pytest.approx([0.04, 0.08, 0.16, 0.32, 0.64])
    assert waits[-1] == pytest.approx(MINUTE.total_seconds())

    # And one answer puts it back to looking promptly.
    monkeypatch.undo()
    await worker.until_something_is_due()
    monkeypatch.setattr(runner, "next_due", refuse)
    assert await worker.until_something_is_due() == pytest.approx(0.02)


async def test_a_worker_on_a_suspending_database_listens_for_nothing(
    session_factory,
):
    engine = create_async_engine(ASYNC_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    listened = []

    try:
        async with run_workflows(factory, workflows=[Resting], suspends_when_idle=True):
            rt = runtime.current()
            # A held LISTEN is a connection a database that suspends itself
            # counts as work, so it keeps the compute up for having asked to be
            # told about nothing. Measured on Neon: with one, it never
            # suspended; without, five minutes after the last query.
            await asyncio.sleep(0.4)
            listened.append(rt.listening.is_set())
    finally:
        await engine.dispose()
    assert listened == [False]


async def test_a_suspending_database_waits_an_hour_unless_told_otherwise(
    session_factory, monkeypatch
):
    built = []
    real = runner.Runner

    def remember(*args, **kwargs):
        """Keep the worker that was built, to see what it was told to wait.

        Args:
            *args: As Runner takes them.
            **kwargs: As Runner takes them.

        Returns:
            The worker.
        """
        worker = real(*args, **kwargs)
        built.append(worker)
        return worker

    monkeypatch.setattr(runner, "Runner", remember)
    engine = create_async_engine(ASYNC_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with run_workflows(factory, workflows=[Resting]):
            pass
        # Long against the few minutes such a database waits before going down,
        # so most of an idle hour is spent with it down rather than woken by a
        # worker looking.
        async with run_workflows(factory, workflows=[Resting], suspends_when_idle=True):
            pass
        # Still the caller's to set, where they know better than the default.
        async with run_workflows(
            factory,
            workflows=[Resting],
            suspends_when_idle=True,
            max_idle_interval=datetime.timedelta(minutes=5),
        ):
            pass

        assert [worker.max_idle_interval for worker in built] == [
            datetime.timedelta(seconds=30),
            datetime.timedelta(hours=1),
            datetime.timedelta(minutes=5),
        ]

        # And asking to listen cheaply on a database that charges for being up
        # is refused rather than resolved one way without saying so.
        with pytest.raises(ValueError, match="listen_engine cannot be used"):
            async with run_workflows(
                factory,
                workflows=[Resting],
                suspends_when_idle=True,
                listen_engine=engine,
            ):
                pass
    finally:
        await engine.dispose()


async def test_a_worker_that_cannot_listen_waits_as_long_as_one_that_can(
    session_factory,
):
    rt = runtime.current()
    worker = runner.Runner(
        rt, [Resting], 4, datetime.timedelta(milliseconds=20), max_idle_interval=MINUTE
    )
    await Resting.by().cancel()
    was = rt.listening.is_set()
    try:
        # Nothing is scheduled, so there is nothing to wait for either way.
        rt.listening.set()
        assert await worker.until_something_is_due() == pytest.approx(
            MINUTE.total_seconds()
        )

        rt.listening.clear()
        # The same deaf. What the database was asked already covers every timer,
        # retry, schedule and lease it knows about, so losing the ear delays
        # only what another process writes meanwhile -- and asking every poll
        # interval through an idle night, to find that out sooner, is what
        # stops a database that bills for being awake from ever sleeping.
        assert await worker.until_something_is_due() == pytest.approx(
            MINUTE.total_seconds()
        )
    finally:
        rt.listening.set() if was else rt.listening.clear()


async def test_a_listener_that_drops_wakes_the_worker_it_was_listening_for():
    nowhere = create_async_engine(
        "postgresql+psycopg://postgres@127.0.0.1:1/nothing_here"
    )
    sessions = async_sessionmaker(nowhere, expire_on_commit=False)
    rt = runtime.Runtime(sessions, asyncio.Event(), LEASE)
    rt.listening.set()
    try:
        # It cannot connect, so it is deaf from the start.
        assert (await notify.listen_once(rt, frozenset(), sessions)).again
    finally:
        await nowhere.dispose()

    assert not rt.listening.is_set()
    # Woken too: a worker that went to sleep while the listener was up has to
    # be told, or it lies there for the whole wait it chose on that basis.
    assert rt.wake.is_set()


async def test_a_listener_that_keeps_failing_waits_longer_each_time(monkeypatch):
    waits: list[float] = []
    # Captured before the patch: the stand-in still has to yield, and calling
    # the patched name would be calling itself.
    real_sleep = asyncio.sleep

    async def record(seconds):
        """Note the wait instead of taking it.

        Args:
            seconds: How long the listener wanted to wait.

        Raises:
            RuntimeError: Once enough attempts have been seen, to end the loop.
        """
        waits.append(seconds)
        await real_sleep(0)
        if len(waits) >= 6:
            msg = "enough"
            raise RuntimeError(msg)

    monkeypatch.setattr(notify.asyncio, "sleep", record)
    nowhere = create_async_engine(
        "postgresql+psycopg://postgres@127.0.0.1:1/nothing_here"
    )
    rt = runtime.Runtime(
        async_sessionmaker(nowhere, expire_on_commit=False), asyncio.Event(), LEASE
    )
    cap = datetime.timedelta(seconds=8)
    try:
        with contextlib.suppress(RuntimeError):
            await notify.wake_on_notify(rt, ["wf_test_resting"], nowhere, cap)
    finally:
        await nowhere.dispose()

    # A database that suspends when nothing asks closes this connection on the
    # way down, so a listener that came straight back would wake it again every
    # time -- for as long as the app is idle.
    assert waits == [1, 2, 4, 8, 8, 8]
    assert waits[-1] == cap.total_seconds()


async def test_a_listener_that_was_up_starts_from_the_short_wait_again(
    monkeypatch,
):
    waits: list[float] = []
    real_sleep = asyncio.sleep
    # Up, up, then never again: the first two broke a connection that worked.
    heard = iter([True, True, False, False, False])

    async def attempt(_runtime, _tables, _sessions):
        """Stand in for an attempt that ended a particular way.

        Args:
            _runtime: The running engine.
            _tables: The tables to wake for.
            _sessions: Where the connection comes from.

        Returns:
            How the attempt ended.
        """
        await real_sleep(0)
        return notify.Attempt(True, next(heard))

    async def record(seconds):
        """Note the wait instead of taking it.

        Args:
            seconds: How long the listener wanted to wait.

        Raises:
            RuntimeError: Once enough attempts have been seen, to end the loop.
        """
        waits.append(seconds)
        await real_sleep(0)
        if len(waits) >= 5:
            msg = "enough"
            raise RuntimeError(msg)

    monkeypatch.setattr(notify, "listen_once", attempt)
    monkeypatch.setattr(notify.asyncio, "sleep", record)
    rt = runtime.Runtime(
        async_sessionmaker(create_async_engine(ASYNC_URL), expire_on_commit=False),
        asyncio.Event(),
        LEASE,
    )
    with contextlib.suppress(RuntimeError):
        await notify.wake_on_notify(
            rt, ["wf_test_resting"], None, datetime.timedelta(seconds=8)
        )

    # A connection that worked and then broke says nothing about the next one,
    # so it is tried again at once; only a database that will not answer at all
    # is worth backing off from.
    assert waits == [1, 1, 1, 2, 4]


async def test_a_listener_never_waits_longer_than_it_was_capped_at(monkeypatch):
    waits: list[float] = []
    real_sleep = asyncio.sleep

    async def record(seconds):
        """Note the wait instead of taking it.

        Args:
            seconds: How long the listener wanted to wait.

        Raises:
            RuntimeError: Once enough attempts have been seen, to end the loop.
        """
        waits.append(seconds)
        await real_sleep(0)
        if len(waits) >= 3:
            msg = "enough"
            raise RuntimeError(msg)

    monkeypatch.setattr(notify.asyncio, "sleep", record)
    nowhere = create_async_engine(
        "postgresql+psycopg://postgres@127.0.0.1:1/nothing_here"
    )
    rt = runtime.Runtime(
        async_sessionmaker(nowhere, expire_on_commit=False), asyncio.Event(), LEASE
    )
    try:
        with contextlib.suppress(RuntimeError):
            # Capped below the first wait, which a worker told to poll fast
            # would be.
            await notify.wake_on_notify(
                rt, ["wf_test_resting"], nowhere, datetime.timedelta(milliseconds=200)
            )
    finally:
        await nowhere.dispose()

    assert waits == [0.2, 0.2, 0.2]


async def test_a_listener_that_keeps_failing_wakes_the_worker_once():
    nowhere = create_async_engine(
        "postgresql+psycopg://postgres@127.0.0.1:1/nothing_here"
    )
    sessions = async_sessionmaker(nowhere, expire_on_commit=False)
    rt = runtime.Runtime(sessions, asyncio.Event(), LEASE)
    try:
        # It was never listening, so nothing was decided on the strength of it.
        assert (await notify.listen_once(rt, frozenset(), sessions)).again
        assert not rt.wake.is_set()

        rt.listening.set()
        assert (await notify.listen_once(rt, frozenset(), sessions)).again
        assert rt.wake.is_set()

        # Retrying while still deaf: the worker is already polling, and waking
        # it every second is the traffic a long poll interval exists to avoid.
        rt.wake.clear()
        assert (await notify.listen_once(rt, frozenset(), sessions)).again
        assert not rt.wake.is_set()
    finally:
        await nowhere.dispose()
