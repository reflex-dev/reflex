"""Tests for running attempts from different runs at the same time."""

import asyncio
import contextlib

from reflex_base.workflow import WorkflowConfig, manual

import reflex as rx
from reflex.workflow.records import RunStatus
from reflex.workflow.runtime import WorkflowRuntime
from reflex.workflow.store import MemoryRunStore


def _slow_flow(peak: list[int], live: list[int]):
    """Build a workflow whose step records how many run at once.

    Args:
        peak: Collects the highest observed concurrency.
        live: Tracks currently executing attempts.

    Returns:
        The workflow class.
    """

    class Slow(rx.State):
        __workflow__ = WorkflowConfig(id="conc.slow")
        n: int = 0

        @rx.event(durable=True, trigger=manual(), effect="read")
        async def go(self, n: int):
            """Hold the step open long enough to overlap with siblings.

            Args:
                n: An identifier for the run.
            """
            live.append(1)
            peak.append(len(live))
            await asyncio.sleep(0.15)
            live.pop()
            self.n = n

    return Slow


async def test_steps_of_different_runs_execute_concurrently(
    forked_registration_context,
):
    """Throughput must not be one step at a time for the whole process."""
    peak: list[int] = []
    live: list[int] = []
    flow = _slow_flow(peak, live)

    runtime = WorkflowRuntime(MemoryRunStore(), poll_interval=0.01, max_concurrency=4)
    runtime.register(flow)
    async with runtime.running():
        results = [await runtime.kernel.start(flow.go(index)) for index in range(4)]
        snapshots = []
        for _ in range(200):
            snapshots = [
                await runtime.kernel.get_run(result.run_id)
                for result in results
                if result.run_id is not None
            ]
            if all(
                snapshot is not None and snapshot.status is RunStatus.COMPLETED
                for snapshot in snapshots
            ):
                break
            await asyncio.sleep(0.02)

        assert all(
            snapshot is not None and snapshot.status is RunStatus.COMPLETED
            for snapshot in snapshots
        )
        assert max(peak) > 1, "attempts never overlapped"


async def test_concurrency_is_bounded(forked_registration_context):
    """The kernel must not start more attempts than its limit allows."""
    peak: list[int] = []
    live: list[int] = []
    flow = _slow_flow(peak, live)

    runtime = WorkflowRuntime(MemoryRunStore(), poll_interval=0.01, max_concurrency=2)
    runtime.register(flow)
    async with runtime.running():
        results = [await runtime.kernel.start(flow.go(index)) for index in range(6)]
        snapshots = []
        for _ in range(300):
            snapshots = [
                await runtime.kernel.get_run(result.run_id)
                for result in results
                if result.run_id is not None
            ]
            if all(
                snapshot is not None and snapshot.status is RunStatus.COMPLETED
                for snapshot in snapshots
            ):
                break
            await asyncio.sleep(0.02)

        assert max(peak) <= 2
        assert all(
            snapshot is not None and snapshot.status is RunStatus.COMPLETED
            for snapshot in snapshots
        )


async def test_one_run_still_runs_its_steps_in_order(forked_registration_context):
    """Concurrency is across runs; a run's own mailbox stays serial."""
    order: list[str] = []

    class Serial(rx.State):
        __workflow__ = WorkflowConfig(id="conc.serial")
        seen: int = 0

        @rx.event(durable=True, trigger=manual(), effect="none")
        async def first(self):
            """Run first.

            Returns:
                The second step.
            """
            order.append("first")
            await asyncio.sleep(0.05)
            return Serial.second

        @rx.event(durable=True, effect="none")
        async def second(self):
            """Run second."""
            order.append("second")

    runtime = WorkflowRuntime(MemoryRunStore(), poll_interval=0.01, max_concurrency=8)
    runtime.register(Serial)
    async with runtime.running():
        result = await runtime.kernel.start(Serial.first)
        assert result.run_id is not None
        for _ in range(200):
            snapshot = await runtime.kernel.get_run(result.run_id)
            if snapshot is not None and snapshot.status is RunStatus.COMPLETED:
                break
            await asyncio.sleep(0.02)
        assert order == ["first", "second"]


class _Idle(rx.State):
    """A workflow that is never started, so the worker only polls."""

    __workflow__ = WorkflowConfig(id="conc.idle")

    @rx.event(durable=True, trigger=manual(), effect="none")
    def go(self):
        """Do nothing."""


async def test_the_worker_dies_when_its_task_is_cancelled(
    forked_registration_context,
):
    """Cancelling the worker task must stop it, without going through aclose.

    Not everything that stops a worker calls aclose: a supervisor, a task
    group, or an event loop being torn down all just cancel the task. A loop
    that treats cancellation as a retryable error goes back to polling, and
    then nothing can stop it -- the process hangs on shutdown waiting for a
    task that has already resumed work.
    """
    runtime = WorkflowRuntime(MemoryRunStore(), poll_interval=0.05)
    runtime.register(_Idle)
    await runtime.startup()
    worker = runtime.kernel._worker
    assert worker is not None
    # Let the loop reach its idle wait, which is where a shutdown finds it.
    await asyncio.sleep(0.15)

    worker.cancel()
    for _ in range(40):
        if worker.done():
            break
        await asyncio.sleep(0.05)

    assert worker.done(), "the worker went back to polling after being cancelled"
    with contextlib.suppress(asyncio.CancelledError):
        await worker
    await runtime.shutdown()
