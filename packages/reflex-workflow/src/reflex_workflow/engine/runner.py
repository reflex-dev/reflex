"""The worker loop: claim due rows, run their steps, and shut down cleanly."""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import logging
from collections.abc import AsyncIterator, Collection, Iterable, Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from reflex_workflow.engine.claim import claim, next_due
from reflex_workflow.engine.execute import Lease, execute, release
from reflex_workflow.engine.notify import wake_on_notify
from reflex_workflow.engine.runtime import Runtime, replace_current
from reflex_workflow.model import DEFAULT_LANE, REGISTRY, Workflow, steps_in

logger = logging.getLogger(__name__)

# How long a cancelled step's row is given to be handed back on the way out.
GIVE_BACK = datetime.timedelta(seconds=5)

# The longest a worker waits when the database says nothing is due at all.
DEFAULT_MAX_IDLE = datetime.timedelta(seconds=30)


class Runner:
    """Claims due rows and runs their steps, a bounded number at a time."""

    def __init__(
        self,
        runtime: Runtime,
        workflows: Sequence[type[Workflow]],
        max_concurrency: int,
        poll_interval: datetime.timedelta,
        lanes: Collection[str] = (DEFAULT_LANE,),
        max_idle_interval: datetime.timedelta = DEFAULT_MAX_IDLE,
    ) -> None:
        """Set up a runner; ``loop`` starts it.

        Args:
            runtime: The engine state the runner works with.
            workflows: The workflow classes it runs.
            max_concurrency: Steps it runs at once.
            poll_interval: How often to look for due rows when nothing wakes it.
            lanes: The lanes this worker serves; steps in other lanes are left
                for the workers that do.
            max_idle_interval: The longest it waits when nothing is due.
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
        self.max_idle_interval = max_idle_interval
        self.inflight: set[asyncio.Task[str]] = set()
        # The row and lease behind each running step, so one this worker
        # cancels on the way out can be given back rather than left held.
        self.holding: dict[
            asyncio.Task[str], tuple[type[Workflow], list[Any], Lease]
        ] = {}
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
            # asyncio's own TimeoutError, which is only the builtin from 3.11 on.
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(wake.wait(), await self.until_something_is_due())

    async def until_something_is_due(self) -> float:
        """Return how long to wait before looking again, when nothing was taken.

        The database is asked when its next run comes due, so a worker with
        nothing to do sleeps until then instead of asking again every interval.
        That is what lets a database that bills for being awake, or suspends
        itself when it is not, go quiet between runs.

        Bounded both ways: never below ``poll_interval``, since a run that is
        due but could not be claimed -- one held back by a limit, or by this
        worker being full -- would otherwise be asked for in a tight loop; and
        never above ``max_idle_interval``, which is also how long a worker waits
        when nothing at all is scheduled.

        Returns:
            Seconds to wait.
        """
        floor, cap = self.poll_interval, self.max_idle_interval
        try:
            due = await next_due(self.runtime, self.workflows, self.runnable)
        except Exception:
            # A table that cannot be asked is not a reason to spin on it.
            logger.exception("reflex_workflow could not ask when work is next due")
            return cap.total_seconds()
        if due is None:
            return cap.total_seconds()
        return min(max(due, floor), cap).total_seconds()

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
    max_idle_interval: datetime.timedelta = DEFAULT_MAX_IDLE,
    listen_engine: AsyncEngine | None = None,
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
        max_idle_interval: The longest to wait when nothing is scheduled at all.
            Between runs a worker sleeps until the database says the next one is
            due, so this is what it costs an idle database: set it above the
            point a database suspends itself and the workers will not hold it
            open. Work written by another process is waited for at most this
            long, unless NOTIFY reaches this worker first.
        listen_engine: Where to listen for those notifications, when that cannot
            be where the steps run. A pooler in transaction mode -- Neon's
            pooled endpoint, PgBouncer -- cannot hold a LISTEN, so point this at
            the direct endpoint and leave the pooled one to the steps.

    Yields:
        Nothing; steps run while the block is active.

    Raises:
        ValueError: If ``max_concurrency`` is below one, ``lease`` or
            ``poll_interval`` is not positive, or ``max_idle_interval`` is
            shorter than ``poll_interval``.
    """
    # A lease of nothing expires as it is taken, letting two workers run one
    # step at once; the others would leave a worker that never runs anything.
    if max_concurrency < 1:
        msg = f"max_concurrency must be at least 1; got {max_concurrency}."
        raise ValueError(msg)
    if (
        lease <= datetime.timedelta()
        or poll_interval <= datetime.timedelta()
        or max_idle_interval < poll_interval
    ):
        msg = (
            "lease and poll_interval must be positive, and max_idle_interval "
            "cannot be shorter than poll_interval."
        )
        raise ValueError(msg)
    runtime = Runtime(session_factory, asyncio.Event(), lease)
    previous = replace_current(runtime)
    runner = Runner(
        runtime,
        list(workflows) if workflows is not None else list(REGISTRY.values()),
        max_concurrency,
        poll_interval,
        lanes,
        max_idle_interval,
    )
    loop = asyncio.create_task(runner.loop())
    ear = asyncio.create_task(
        wake_on_notify(
            runtime,
            [cls.__tablename__ for cls in runner.workflows],
            listen_engine,
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
            ear.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await ear
            replace_current(previous)


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
