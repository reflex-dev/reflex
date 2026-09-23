"""Tests for reflex_workflow.engine.runner, end to end against a real Postgres.

Set REFLEX_TEST_POSTGRES to a postgresql:// URL for a database the tests may wipe.
"""

from __future__ import annotations

import asyncio
import collections
import contextlib
import datetime
import inspect
import os
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
import pytest_asyncio
from sqlalchemy import String, func, insert, select, update
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
from reflex_workflow.engine import claim, execute, notify, runner, runtime  # noqa: E402

LEASE = datetime.timedelta(seconds=2)

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
    assert row.wake_at > datetime.datetime.now(
        datetime.timezone.utc
    ) - datetime.timedelta(seconds=1)
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
    now = datetime.datetime.now(datetime.timezone.utc)
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
        return all([await status_is(Racer, key, "done")() for key in keys])

    try:
        await wait_until(all_done)
    finally:
        for worker in workers:
            await worker.drain(datetime.timedelta(seconds=5))
        for loop in loops:
            loop.cancel()
        await asyncio.gather(*loops, return_exceptions=True)
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
    [(pk, first_claim)] = await claim.claim(rt, Gated, 1)
    stale = asyncio.create_task(execute.execute(rt, Gated, pk, first_claim))
    await wait_until(lambda: f"gated-start:{key}" in EVENTS)

    # The first worker stalls past its lease, and a second worker takes the row over.
    async with session_factory() as session, session.begin():
        await session.execute(
            update(Gated)
            .where(Gated.key == key)
            .values(claimed_until=func.now() - datetime.timedelta(seconds=1))
        )
    [(_, second_claim)] = await claim.claim(rt, Gated, 1)
    fresh = asyncio.create_task(execute.execute(rt, Gated, pk, second_claim))
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


async def test_an_event_beats_a_timeout_that_is_already_running(session_factory):
    key = uuid.uuid4().hex
    rt = runtime.current()
    await RaceReview(key=key).start(RaceReview.submit(timeout_s=1, expire_pause_s=2))
    pk = await arm_wait(key)

    # A worker claims the timeout, and the decision lands while it is running.
    await asyncio.sleep(1.1)
    timing_out = await claim_row(RaceReview, pk)
    expiring = asyncio.create_task(execute.execute(rt, RaceReview, pk, timing_out))
    await wait_until(lambda: f"expire-start:{key}" in EVENTS)
    handle = RaceReview.by(RaceReview.key == key)
    assert await handle.deliver(RaceReview.decide("approve")) == 1
    assert await expiring == "fenced"

    # The expiry ran, but nothing it did to the row was kept: the decision wins.
    assert await step_row(RaceReview, pk) == "ok"
    assert await status_is(RaceReview, key, "decided:approve:manager")()
    row = await handle.get()
    assert row is not None
    assert (row.next_step, row.waiting_for, row.pending_event) == (None, None, None)


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
    cls: type[RaceReview | Repeating | Batch | Parked | Piece], pk: list[int]
) -> int:
    """Claim one row the way the engine does, by primary key.

    Args:
        cls: The workflow class.
        pk: The row's primary key.

    Returns:
        The version this claim holds.
    """
    stmt = (
        update(cls)
        .where(cls.id == pk[0])
        .values(claimed_until=func.now() + LEASE, wf_version=cls.wf_version + 1)
        .returning(cls.wf_version)
        .execution_options(synchronize_session=False)
    )
    async with runtime.current().session_factory() as session, session.begin():
        return (await session.execute(stmt)).scalar_one()


async def pk_of(
    cls: type[RaceReview | Repeating | Batch | Parked | Piece], key: str
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
    cls: type[RaceReview | Repeating | Batch | Parked | Piece], pk: list[int]
) -> str:
    """Claim and run one step of a row.

    Args:
        cls: The workflow class.
        pk: The row's primary key.

    Returns:
        The step's outcome.
    """
    return await execute.execute(runtime.current(), cls, pk, await claim_row(cls, pk))


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
    minute = datetime.timedelta(minutes=1)
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
    assert row.wake_at > datetime.datetime.now(datetime.timezone.utc)


async def test_a_cron_schedule_sets_the_next_time_it_names(session_factory):
    key = uuid.uuid4().hex
    pk = await insert_repeating(key, "cron", datetime.timedelta(seconds=1))
    assert await step_row(Repeating, pk) == "ok"

    row = await Repeating.by(Repeating.key == key).get()
    assert row is not None
    assert row.wake_at is not None
    wake_at = row.wake_at.astimezone(datetime.timezone.utc)
    now = datetime.datetime.now(datetime.timezone.utc)
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
    splitting = asyncio.create_task(execute.execute(rt, Batch, pk, claimed))
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
        rows = await Tenant.by(Tenant.key.in_(keys)).all()
        return len(rows) == len(keys) and all(row.status == "done" for row in rows)

    try:
        await wait_until(all_done, timeout=60)
    finally:
        for worker in workers:
            await worker.drain(datetime.timedelta(seconds=5))
        for loop in loops:
            loop.cancel()
        await asyncio.gather(*loops, return_exceptions=True)
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
        await worker.drain(datetime.timedelta(seconds=5))
        loop.cancel()
        await asyncio.gather(loop, return_exceptions=True)
        await engine.dispose()


async def test_a_rate_limit_lets_through_a_burst_then_refills(session_factory):
    STARTS.clear()
    provider = f"provider-{uuid.uuid4().hex}"
    started = time.monotonic()
    await start_many(Metered, provider, 8, provider=provider)

    async def all_done() -> bool:
        rows = await Metered.by(Metered.provider == provider).all()
        return len(rows) == 8 and all(row.status == "done" for row in rows)

    await wait_until(all_done, timeout=60)
    times = sorted(t - started for t in STARTS[provider])
    # Four at once from a full bucket, then the rest as it refills: two a second.
    assert len(times) == 8
    assert times[3] < 1
    assert times[7] >= 1.5


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
        rows = await Metered.by(Metered.provider == provider).all()
        return len(rows) == 6 and all(row.status == "done" for row in rows)

    try:
        await wait_until(all_done, timeout=60)
    finally:
        for worker in workers:
            await worker.drain(datetime.timedelta(seconds=5))
        for loop in loops:
            loop.cancel()
        await asyncio.gather(*loops, return_exceptions=True)
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
        for worker, _ in made:
            await worker.drain(datetime.timedelta(seconds=5))
        for loop in loops:
            loop.cancel()
        await asyncio.gather(*loops, return_exceptions=True)
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
        await worker.drain(datetime.timedelta(seconds=5))
        loop.cancel()
        await asyncio.gather(loop, return_exceptions=True)
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
    running = asyncio.create_task(execute.execute(rt, RaceReview, pk, claimed))
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
    assert all(attempt.run != [key] for attempt in written)
