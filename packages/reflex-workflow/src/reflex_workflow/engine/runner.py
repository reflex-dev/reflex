"""The worker loop: claim due rows, run their steps, and shut down cleanly."""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import enum
import logging
from collections.abc import (
    AsyncIterator,
    Awaitable,
    Callable,
    Collection,
    Iterable,
    Sequence,
)
from typing import Any, TypeAlias

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from reflex_workflow.engine.claim import claim, next_due
from reflex_workflow.engine.execute import Lease, execute, release
from reflex_workflow.engine.notify import wake_on_notify
from reflex_workflow.engine.runtime import Runtime, current, replace_current
from reflex_workflow.model import DEFAULT_LANE, REGISTRY, Workflow, steps_in

logger = logging.getLogger(__name__)

# Told the instant a worker is next waiting for, or None when it is waiting for
# nothing. Awaited on the worker's own loop, so it should return promptly.
OnIdle: TypeAlias = "Callable[[datetime.datetime | None], Awaitable[None]]"


class UnsetType(enum.Enum):
    """The type of ``UNSET``, so it narrows where it is compared against."""

    UNSET = enum.auto()


# Not None, which is a real answer here: nothing is scheduled.
UNSET = UnsetType.UNSET

# How long a cancelled step's row is given to be handed back on the way out.
GIVE_BACK = datetime.timedelta(seconds=5)

# The longest a worker waits when the database says nothing is due at all, and
# the same for a database that suspends itself: long against the few minutes
# such a database waits before going down, so most of an idle hour is spent with
# it down rather than woken again by the worker looking.
DEFAULT_MAX_IDLE = datetime.timedelta(seconds=30)
SUSPENDING_MAX_IDLE = datetime.timedelta(hours=1)


class Runner:
    """Claims due rows and runs their steps, a bounded number at a time."""

    def __init__(
        self,
        runtime: Runtime,
        workflows: Sequence[type[Workflow]],
        max_concurrency: int,
        poll_interval: datetime.timedelta,
        lanes: Collection[str] = (DEFAULT_LANE,),
        max_idle_interval: datetime.timedelta | None = None,
        on_idle: OnIdle | None = None,
    ) -> None:
        """Set up a runner; ``loop`` starts it.

        Args:
            runtime: The engine state the runner works with.
            workflows: The workflow classes it runs.
            max_concurrency: Steps it runs at once.
            poll_interval: How often to look for due rows when nothing wakes it.
            lanes: The lanes this worker serves; steps in other lanes are left
                for the workers that do.
            max_idle_interval: The longest it waits when nothing is due;
                thirty seconds by default, or ``poll_interval`` when that is
                longer, since a worker never waits less than it was told to.
            on_idle: Told when the instant this worker is waiting for changes.
        """
        self.runtime = runtime
        self.lanes = frozenset(lanes)
        # What this worker may run of each table: None when it may run all of it,
        # and a table it can run nothing of is left out entirely.
        self.runnable: dict[type[Workflow], list[str] | None] = {}
        for cls in workflows:
            names = steps_in(cls, self.lanes)
            if not names:
                continue
            self.runnable[cls] = (
                None if len(names) == len(cls.__workflow_steps__) else names
            )
        self.workflows = [cls for cls in workflows if cls in self.runnable]
        self.max_concurrency = max_concurrency
        self.poll_interval = poll_interval
        self.max_idle_interval = max_idle_interval or max(
            DEFAULT_MAX_IDLE, poll_interval
        )
        self.inflight: set[asyncio.Task[str]] = set()
        # The row and lease behind each running step, so one this worker
        # cancels on the way out can be given back rather than left held.
        self.holding: dict[
            asyncio.Task[str], tuple[type[Workflow], list[Any], Lease]
        ] = {}
        self.on_idle = on_idle
        # The last instant handed to on_idle, so the same answer asked again is
        # not reported as news. Unset until the first pass, which is not the
        # same as knowing there is nothing scheduled.
        self.reported: datetime.datetime | UnsetType | None = UNSET
        # What the last pass that could ask nothing at all waited, doubled each
        # time it happens again; None once a pass gets an answer. The wait
        # itself rather than a count of them, so nothing has to raise two to
        # the power of how long a database has been down.
        self.unanswered: datetime.timedelta | None = None
        self.stopping = False
        # Where the next pass starts, so a busy table cannot always go first.
        self.turn = 0

    async def _claim_from(self, cls: type[Workflow], limit: int) -> int:
        """Claim and start due steps of one workflow table.

        Args:
            cls: The workflow class.
            limit: Most steps to start.

        Returns:
            How many steps were started.
        """
        try:
            claimed = await claim(self.runtime, cls, limit, self.runnable[cls])
        except Exception:
            # One broken table (not migrated yet, say) must not stop the others.
            logger.exception(
                "reflex_workflow could not claim from %s", cls.__qualname__
            )
            return 0
        for taken in claimed:
            held = Lease(taken.until)
            task = asyncio.create_task(
                execute(self.runtime, cls, taken.pk, taken.version, held)
            )
            self.inflight.add(task)
            self.holding[task] = (cls, taken.pk, held)
            task.add_done_callback(self._finished)
        return len(claimed)

    def _finished(self, task: asyncio.Task[str]) -> None:
        self.inflight.discard(task)
        # A step that ran to the end has settled its own lease.
        if not task.cancelled():
            self.holding.pop(task, None)
        self.runtime.wake.set()
        if not task.cancelled() and (err := task.exception()) is not None:
            logger.error(
                "reflex_workflow step failed outside its handler", exc_info=err
            )

    def _order(self) -> list[type[Workflow]]:
        """Return the tables to visit this pass, starting where the last one left off.

        Returns:
            Every workflow, rotated by one place from the previous pass.
        """
        count = len(self.workflows)
        if not count:
            return []
        self.turn = (self.turn + 1) % count
        return [self.workflows[(self.turn + i) % count] for i in range(count)]

    async def loop(self) -> None:
        """Claim and run steps until stopped."""
        wake = self.runtime.wake
        while not self.stopping:
            # Cleared before the pass rather than after it: a wake that lands
            # while the pass is claiming may be for work the pass already looked
            # past, and waiting out the poll would lose it.
            wake.clear()
            started = 0
            order = self._order()
            # A share each, so the first table cannot spend the whole pass; a
            # second lap hands the leftovers to whoever still has work.
            share = max(1, self.max_concurrency // max(1, len(order)))
            for allowance in (share, self.max_concurrency):
                for cls in order:
                    free = min(allowance, self.max_concurrency - len(self.inflight))
                    if free <= 0 or self.stopping:
                        break
                    started += await self._claim_from(cls, free)
            if started:
                continue
            # Asked, and reported, before the pass is counted: a caller holding
            # a request open on that count lets the machine suspend when it
            # returns, and it must not do that until whatever wakes the machine
            # again has been told when to.
            seconds = await self.until_something_is_due()
            # Not while a step it started is still running: suspended now, the
            # machine would cut that step off. Nor when the loop was woken
            # during the pass, by a run started after it looked or a step that
            # finished: there may be work it has not seen. Either way the loop
            # looks again at once, and that pass is counted instead.
            if not self.inflight and not wake.is_set():
                await self.runtime.settled.record()
            # Against the wall clock rather than one timeout of that length: a
            # machine that suspends leaves asyncio's monotonic clock where it
            # found it, so a timer set before the suspend has as long left after
            # it, and the wait would be served late by however long the machine
            # was away.
            until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                seconds=seconds
            )
            while not wake.is_set() and not self.stopping:
                left = (
                    until - datetime.datetime.now(datetime.timezone.utc)
                ).total_seconds()
                if left <= 0:
                    break
                # asyncio's own TimeoutError, only the builtin from 3.11 on.
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(
                        wake.wait(), min(left, self.max_idle_interval.total_seconds())
                    )

    async def until_something_is_due(self) -> float:
        """Return how long to wait before looking again, when nothing was taken.

        The database is asked when its next run comes due, so a worker with
        nothing to do sleeps until then instead of asking again every interval.
        That is what lets a database that bills for being awake, or suspends
        itself when it is not, go quiet between runs.

        A pass that could not ask at all -- every table refusing, which is a
        database that is not answering -- waits the floor, and twice that again
        each time it keeps happening, up to the cap.

        Bounded both ways: never below ``poll_interval``, since a run that is
        due but could not be claimed -- one held back by a limit, or by this
        worker being full -- would otherwise be asked for in a tight loop; and
        never above ``max_idle_interval``, which is also how long a worker waits
        when nothing at all is scheduled.

        The same bounds whether or not this worker is listening. What the
        database was asked already covers everything the table knows about --
        every timer, every retry, every schedule, and the lease of a worker
        that may have died -- so losing the ear delays only work another
        process writes while this one sleeps, by at most the cap. Polling
        through that at a tight interval would trade a bounded delay for a
        database that is never allowed to be idle.

        Returns:
            Seconds to wait.
        """
        floor = self.poll_interval
        cap = self.max_idle_interval
        try:
            due = await next_due(self.runtime, self.workflows, self.runnable)
        except Exception:
            # Asking failed, which is not the same answer as nothing being due,
            # so the first of these looks again at once: a database coming back
            # from a moment's trouble should not wait out an idle interval it
            # was never asked about. Doubling from there, because the other
            # thing this looks like is a table that was never migrated, which
            # would otherwise be asked after every second for as long as the
            # process lives, and logged each time.
            logger.exception("reflex_workflow could not ask when work is next due")
            self.unanswered = (
                min(floor, cap)
                if self.unanswered is None
                else min(self.unanswered * 2, cap)
            )
            return self.unanswered.total_seconds()
        self.unanswered = None
        await self.report(due.at if due is not None else None)
        if due is None:
            return cap.total_seconds()
        return min(max(due.away, floor), cap).total_seconds()

    async def report(self, at: datetime.datetime | None) -> None:
        """Tell ``on_idle`` when the instant this worker waits for has changed.

        Only on a change, so a caller registering it somewhere else -- a
        platform that wakes a suspended deployment, say -- writes once per
        answer rather than once per pass. The instant comes from the database's
        clock, so it is the same value until the work behind it moves.

        Args:
            at: When the next run comes due, or None when nothing is scheduled.
        """
        if self.on_idle is None or at == self.reported:
            return
        try:
            await self.on_idle(at)
        except Exception:
            # Whatever it does is the application's business, and a worker that
            # stopped claiming because of it would be a far worse failure. Not
            # remembered either, so the next pass tries again rather than
            # treating an answer that never arrived as one already given.
            logger.exception("reflex_workflow on_idle failed")
        else:
            self.reported = at

    def stop(self) -> None:
        """Tell the loop to finish the pass it is in and claim nothing more."""
        self.stopping = True
        self.runtime.wake.set()

    async def drain(self, timeout: datetime.timedelta) -> None:
        """Let running steps finish, then cancel the rest and give their rows back.

        Call it once the loop has stopped, so no step starts after it looked. A
        step that is cancelled has its lease given back, so the run carries on
        under the next worker rather than waiting out a lease nobody holds --
        which is what a deploy in the middle of a long step would otherwise cost
        it. The lease is given back after the step is finished with, and only
        ever the value this worker last wrote, so a row another worker has since
        taken over is left alone.

        Args:
            timeout: How long to wait for running steps.
        """
        if self.inflight:
            await asyncio.wait(self.inflight, timeout=timeout.total_seconds())
        cancelled = list(self.inflight)
        for task in cancelled:
            task.cancel()
        await asyncio.gather(*cancelled, return_exceptions=True)
        holding = [
            row
            for task in cancelled
            if (row := self.holding.pop(task, None)) is not None
        ]
        if holding:
            await self._give_back(holding)

    async def _give_back(
        self, holding: list[tuple[type[Workflow], list[Any], Lease]]
    ) -> None:
        """Hand back the rows of the steps this worker cancelled.

        One budget for all of them rather than one each, so however many were
        running, shutdown is held up by the same amount at most. What is left
        over when it runs out waits out its lease, which is what every row of a
        worker that stopped less politely does anyway.

        Args:
            holding: The row and lease behind each cancelled step.
        """

        async def hand_back() -> None:
            """Give every lease back, in turn, whatever any one of them does."""
            for cls, pk, held in holding:
                try:
                    await release(self.runtime, cls, pk, held)
                except asyncio.CancelledError:  # noqa: PERF203  # once per cancelled row, at shutdown
                    raise
                except Exception:
                    # One row the database will not take back is no reason to
                    # leave the others held for the rest of their leases.
                    logger.exception(
                        "reflex_workflow could not give back a lease on %s",
                        cls.__qualname__,
                    )

        try:
            await asyncio.wait_for(hand_back(), GIVE_BACK.total_seconds())
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            logger.warning(
                "reflex_workflow ran out of time giving back %d lease(s)", len(holding)
            )


@contextlib.asynccontextmanager
async def run_workflows(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    workflows: Iterable[type[Workflow]] | None = None,
    max_concurrency: int = 8,
    poll_interval: datetime.timedelta = datetime.timedelta(seconds=1),
    lease: datetime.timedelta = datetime.timedelta(minutes=5),
    shutdown_timeout: datetime.timedelta = datetime.timedelta(seconds=30),
    lanes: Collection[str] = (DEFAULT_LANE,),
    max_idle_interval: datetime.timedelta | None = None,
    listen_engine: AsyncEngine | None = None,
    on_idle: OnIdle | None = None,
    suspends_when_idle: bool = False,
) -> AsyncIterator[None]:
    """Run workflow steps in this process for the lifetime of the block.

    Enter it from the app's lifespan. Several processes can run it against the same
    database; each claims different rows.

    Args:
        session_factory: Session factory for the database holding the workflow tables.
        workflows: Workflow classes this process runs; defaults to every defined one.
        max_concurrency: Steps this process runs at once.
        poll_interval: How soon it looks again when something is due but could
            not be taken -- held back by a limit, or by this worker being full.
            Starts and runs from this process wake it immediately.
        lease: How long a claim lasts without renewal; a crashed worker's steps run
            again after it expires. Renewed while a step runs.
        shutdown_timeout: How long to let the claim in progress and the running
            steps finish on exit.
        lanes: The lanes this process serves. A step declared in another lane is
            left alone, so a worker with a GPU can be the only one that renders
            and an ordinary one carries on with the rest.
        max_idle_interval: The longest to wait when nothing is scheduled at all;
            thirty seconds by default, an hour under ``suspends_when_idle``, or
            ``poll_interval`` when that is longer. Between runs a worker sleeps
            until the database says the next one is due, so this is what it
            costs an idle database. Work written by another process is waited
            for at most this long, unless NOTIFY reaches this worker first.
        listen_engine: Where to listen for those notifications, when that cannot
            be where the steps run. A pooler in transaction mode -- Neon's
            pooled endpoint, PgBouncer -- cannot hold a LISTEN, so point this at
            the direct endpoint and leave the pooled one to the steps. Not for a
            database that suspends itself: holding the connection is what keeps
            it awake.
        suspends_when_idle: Whether this database stops itself when nothing is
            querying it, and charges for being up -- a managed Postgres like
            Neon. Such a worker listens for nothing, since a held LISTEN is a
            connection the database counts as work, and waits an hour rather
            than thirty seconds, so the time it is asleep is most of the time.
            The cost is that work another process writes waits for the next
            look; everything the table already knows about still comes due when
            it said it would.
        on_idle: Told the instant this worker is next waiting for, and None when
            it is waiting for nothing, each time that answer changes. The
            instant is the database's, so it is the same value until the work
            behind it moves. For a deployment that suspends when idle: register
            it with whatever can wake this process, and pair it with a route
            that calls wake. Awaited on the worker's loop, so it should
            return promptly, and an exception from it is logged and passed over.

    Yields:
        Nothing; steps run while the block is active.

    Raises:
        ValueError: If ``max_concurrency`` is below one, ``lease`` or
            ``poll_interval`` is not positive, a ``max_idle_interval`` was given
            that is shorter than ``poll_interval``, or a ``listen_engine`` was
            given for a database that suspends itself.
    """
    # A lease of nothing expires as it is taken, letting two workers run one
    # step at once; the others would leave a worker that never runs anything.
    if max_concurrency < 1:
        msg = f"max_concurrency must be at least 1; got {max_concurrency}."
        raise ValueError(msg)
    if lease <= datetime.timedelta() or poll_interval <= datetime.timedelta():
        msg = "lease and poll_interval must be positive."
        raise ValueError(msg)
    # Unasked, the runner never waits less than it was told to poll: a worker
    # told to look every minute was allowed to before this existed, and still is.
    if max_idle_interval is not None and max_idle_interval < poll_interval:
        msg = "max_idle_interval cannot be shorter than poll_interval."
        raise ValueError(msg)
    # Refused rather than ignored: the two together read as "listen, cheaply",
    # and what they would do is hold the database open while asking it to sleep.
    if suspends_when_idle and listen_engine is not None:
        msg = (
            "listen_engine cannot be used with suspends_when_idle: holding a "
            "LISTEN is what keeps a database from suspending."
        )
        raise ValueError(msg)
    if suspends_when_idle and max_idle_interval is None:
        max_idle_interval = max(SUSPENDING_MAX_IDLE, poll_interval)
    runtime = Runtime(session_factory, asyncio.Event(), lease)
    previous = replace_current(runtime)
    runner = Runner(
        runtime,
        list(workflows) if workflows is not None else list(REGISTRY.values()),
        max_concurrency,
        poll_interval,
        lanes,
        max_idle_interval,
        on_idle,
    )
    loop = asyncio.create_task(runner.loop())
    # No ear at all where the database suspends itself: the connection one is
    # held on is work as far as that database is concerned, so a worker with
    # nothing to do would keep it up for having asked to be told about nothing.
    ear = (
        None
        if suspends_when_idle
        else asyncio.create_task(
            wake_on_notify(
                runtime,
                [cls.__tablename__ for cls in runner.workflows],
                listen_engine,
                # No point trying more often than the worker would look anyway.
                runner.max_idle_interval,
            )
        )
    )
    try:
        yield
    finally:
        # The loop finishes the claim it is making rather than being cancelled
        # in it: a claim that has committed has leased its rows, and cancelled
        # there they would wait out the lease instead of running.
        runner.stop()
        # One deadline for all of it: a claim that cannot finish -- a database
        # that stopped answering -- is cancelled when it passes, rather than
        # holding shutdown up for good.
        deadline = asyncio.get_running_loop().time() + shutdown_timeout.total_seconds()
        try:
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(loop, shutdown_timeout.total_seconds())
        finally:
            left = max(0.0, deadline - asyncio.get_running_loop().time())
            await runner.drain(datetime.timedelta(seconds=left))
            if ear is not None:
                ear.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await ear
            replace_current(previous)


# How many callers may wait on one worker at once. A second caller asks for
# nothing the first has not already asked for, so past this the rest are left
# to ask again rather than held open alongside them.
WAITERS = 8

_waiting = 0


async def wake(timeout: datetime.timedelta) -> bool:
    """Make the worker in this process look now, and wait for it to catch up.

    For a deployment that suspends when it is idle: something outside it -- a
    platform that knows when this app's next run is due -- reaches a route that
    calls this, and the request is held open until the work has been taken or
    there is nothing to take. Holding it open is the point on hosts that only
    give an instance CPU while it is answering a request.

    Caught up means a pass that claimed nothing while no step it started was
    still running, which is the worker saying there is nothing it can take and
    nothing left to finish: either nothing is due, or what is due is held back
    by a limit and waiting longer would not help.

    Safe to call from anywhere, as often as anyone likes: it asks the worker to
    look, which it would do anyway. Past ``WAITERS`` callers at once the rest
    are not queued behind callers asking for the same thing: they still ask the
    worker to look, and report that they did not see it catch up, since they
    did not.

    Args:
        timeout: The longest to wait for that pass.

    Returns:
        Whether the worker caught up in time.
    """
    global _waiting
    runtime = current()
    settled = runtime.settled
    if _waiting >= WAITERS:
        # Told to look, but not told it caught up: this caller has watched
        # nothing, and saying otherwise would have a host suspend on the word
        # of a request that waited for no answer at all.
        runtime.wake.set()
        return False
    async with settled.changed:
        seen = settled.passes
    _waiting += 1
    try:
        runtime.wake.set()
        return await settled.after(seen, timeout)
    finally:
        _waiting -= 1


@contextlib.asynccontextmanager
async def connect_workflows(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    lease: datetime.timedelta = datetime.timedelta(minutes=5),
) -> AsyncIterator[None]:
    """Address workflow runs from a process that does not run them.

    A web process that starts runs, delivers approvals and reads their state needs
    the database, not a worker. Enter this from its lifespan instead of
    ``run_workflows``, and leave the running to the processes that do it.

    A run started or advanced from here is announced to the workers with
    Postgres ``NOTIFY``, so they pick it up at once rather than at their next
    poll.

    Args:
        session_factory: Session factory for the database holding the workflow
            tables.
        lease: How long a claim lasts, for the workers that do run steps; it only
            matters here if this process later runs one itself.

    Yields:
        Nothing; runs can be addressed while the block is active.
    """
    previous = replace_current(Runtime(session_factory, asyncio.Event(), lease))
    try:
        yield
    finally:
        replace_current(previous)
