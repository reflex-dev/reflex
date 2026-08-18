"""Tests for claim leases, which keep a second worker off a live claim."""

import asyncio

import pytest
from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import WorkflowConfig, manual

import reflex as rx
from reflex.workflow.definition import compile_workflow
from reflex.workflow.kernel import WorkflowKernel
from reflex.workflow.records import HistoryEventType, RunStatus, StepStatus
from reflex.workflow.store import MemoryRunStore, SqliteRunStore
from reflex.workflow.testing import WorkflowTestHarness


class _Clock:
    """A manually advanced epoch-seconds clock shared by cooperating kernels."""

    def __init__(self, now: float = 1_000_000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


async def _drain(pump: asyncio.Task | None, release: asyncio.Event) -> None:
    """Let a pumped kernel finish so stores close without in-flight work.

    Args:
        pump: The task running the kernel's execution loop, if it started.
        release: The event the hanging handler is waiting on.
    """
    release.set()
    if pump is None:
        return
    pump.cancel()
    await asyncio.gather(pump, return_exceptions=True)


async def test_second_kernel_cannot_steal_a_live_claim(
    forked_registration_context, tmp_path
):
    """A peer starting up must not reclaim a claim another worker is executing.

    This is the regression test for the double-execution defect: recovery used
    to treat every CLAIMED row as an orphan, so a second worker booting while
    the first was mid-attempt ran the same step concurrently.
    """
    started = asyncio.Event()
    release = asyncio.Event()
    executions = []

    class LeaseFlow(rx.State):
        __workflow__ = WorkflowConfig(id="lease.steal")
        status: str = "pending"

        @rx.event(durable=True, trigger=manual(), effect="idempotent_write")
        async def charge(self):
            executions.append(1)
            started.set()
            await release.wait()
            self.status = "charged"

    definition = compile_workflow(LeaseFlow)
    db_path = tmp_path / "workflow.db"
    clock = _Clock()
    store_a = SqliteRunStore(db_path)
    store_b = SqliteRunStore(db_path)
    pump: asyncio.Task | None = None
    try:
        kernel_a = WorkflowKernel([definition], store_a, clock=clock)
        kernel_b = WorkflowKernel([definition], store_b, clock=clock)

        result = await kernel_a.start(LeaseFlow.charge())
        assert result.run_id is not None
        pump = asyncio.create_task(kernel_a.run_until_idle())
        await asyncio.wait_for(started.wait(), timeout=5)

        # Kernel B boots while A is inside the handler, holding a live claim.
        assert await kernel_b.recover() == 0
        assert await store_b.claim_next(clock()) is None
        assert len(executions) == 1

        release.set()
        await asyncio.wait_for(pump, timeout=5)

        snapshot = await kernel_a.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state == {"status": "charged"}
        assert snapshot.steps[0].recoveries == 0
        assert len(executions) == 1
    finally:
        await _drain(pump, release)
        store_a.close()
        store_b.close()


async def test_expired_lease_is_reclaimed(forked_registration_context, tmp_path):
    """A claim whose lease has expired is recovered by a peer."""
    started = asyncio.Event()
    release = asyncio.Event()

    class ExpiredFlow(rx.State):
        __workflow__ = WorkflowConfig(id="lease.expired")
        status: str = "pending"

        @rx.event(durable=True, trigger=manual(), effect="read")
        async def work(self):
            started.set()
            await release.wait()
            self.status = "done"

    definition = compile_workflow(ExpiredFlow)
    db_path = tmp_path / "workflow.db"
    clock = _Clock()
    store_a = SqliteRunStore(db_path)
    store_b = SqliteRunStore(db_path)
    try:
        kernel_a = WorkflowKernel(
            [definition], store_a, clock=clock, lease_duration=30.0
        )
        kernel_b = WorkflowKernel(
            [definition], store_b, clock=clock, lease_duration=30.0
        )
        result = await kernel_a.start(ExpiredFlow.work())
        assert result.run_id is not None
        pump = asyncio.create_task(kernel_a.run_until_idle())
        await asyncio.wait_for(started.wait(), timeout=5)

        # Simulate A dying: stop renewing and push the clock past the lease.
        pump.cancel()
        await asyncio.gather(pump, return_exceptions=True)
        clock.now += 31.0

        assert await kernel_b.recover() == 1
        steps = await store_b.get_steps(result.run_id)
        assert steps[0].status is StepStatus.RECOVERY_WAIT
        assert steps[0].recoveries == 1
    finally:
        release.set()
        store_a.close()
        store_b.close()


async def test_in_flight_claim_survives_clock_jumps(forked_registration_context):
    """Advancing virtual time past a lease must not steal this kernel's own claim."""
    started = asyncio.Event()
    release = asyncio.Event()
    executions = []

    class JumpFlow(rx.State):
        __workflow__ = WorkflowConfig(id="lease.jump")
        status: str = "pending"

        @rx.event(durable=True, trigger=manual(), effect="idempotent_write")
        async def work(self):
            executions.append(1)
            started.set()
            await release.wait()
            self.status = "done"

    async with WorkflowTestHarness(JumpFlow, lease_duration="60s") as harness:
        result = await harness.kernel.start(JumpFlow.work())
        assert result.run_id is not None
        pump = asyncio.create_task(harness.run_until_idle())
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
            for _ in range(4):
                await harness.advance("30s")
                steps = await harness.kernel.store.get_steps(result.run_id)
                assert steps[0].status is StepStatus.CLAIMED
                assert steps[0].lease_expires_at == pytest.approx(harness.now + 60.0)
                assert steps[0].recoveries == 0
            assert executions == [1]
        finally:
            release.set()
            await asyncio.wait_for(pump, timeout=5)

        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.steps[0].recoveries == 0
        assert executions == [1]


async def test_lease_loss_abandons_and_then_recovers(
    forked_registration_context, tmp_path
):
    """A fenced attempt commits nothing, and the recovered step runs again."""
    started = asyncio.Event()
    release = asyncio.Event()
    executions = []

    class AbandonFlow(rx.State):
        __workflow__ = WorkflowConfig(id="lease.abandon")
        status: str = "pending"

        @rx.event(durable=True, trigger=manual(), effect="idempotent_write")
        async def work(self):
            executions.append(1)
            if len(executions) == 1:
                started.set()
                await release.wait()
            self.status = "committed"

    definition = compile_workflow(AbandonFlow)
    clock = _Clock()
    store = SqliteRunStore(tmp_path / "workflow.db")
    try:
        kernel = WorkflowKernel(
            [definition],
            store,
            clock=clock,
            lease_duration=30.0,
            lease_renew_interval=0.01,
        )
        result = await kernel.start(AbandonFlow.work())
        assert result.run_id is not None
        pump = asyncio.create_task(kernel.run_until_idle())
        await asyncio.wait_for(started.wait(), timeout=5)

        # A peer reclaims the step once the lease lapses; the renewer notices.
        clock.now += 31.0
        assert (await store.recover_orphans(clock(), max_recoveries=10))[0] == 1
        # The first attempt stays blocked, so only the renewer can end it: it
        # sees the fence, cancels the attempt, and the loop re-runs the step.
        await asyncio.wait_for(pump, timeout=5)

        history = await store.get_history(result.run_id)
        abandoned = [
            event
            for event in history
            if event.type is HistoryEventType.ATTEMPT_ABANDONED
        ]
        assert len(abandoned) == 1
        assert abandoned[0].data["reason"] == "lease_lost"
        assert abandoned[0].data["effect"] == "idempotent_write"

        # The abandoned attempt committed nothing; the recovery did.
        run = await store.get_run(result.run_id)
        assert run is not None
        assert run.status is RunStatus.COMPLETED
        assert run.state_version == 1
        steps = await store.get_steps(result.run_id)
        assert steps[0].recoveries == 1
        assert steps[0].attempts == 0
        assert executions == [1, 1]
    finally:
        release.set()
        store.close()


async def test_shutdown_leaves_the_claim_recoverable(
    forked_registration_context, tmp_path
):
    """Stopping a worker mid-attempt leaves the step claimed, not cancelled."""
    started = asyncio.Event()
    release = asyncio.Event()

    class ShutdownFlow(rx.State):
        __workflow__ = WorkflowConfig(id="lease.shutdown")
        status: str = "pending"

        @rx.event(durable=True, trigger=manual(), effect="read")
        async def work(self):
            started.set()
            await release.wait()
            self.status = "done"

    definition = compile_workflow(ShutdownFlow)
    clock = _Clock()
    store = SqliteRunStore(tmp_path / "workflow.db")
    try:
        kernel = WorkflowKernel(
            [definition], store, clock=clock, lease_duration=30.0, poll_interval=0.01
        )
        result = await kernel.start(ShutdownFlow.work())
        assert result.run_id is not None
        await kernel.start_worker()
        await asyncio.wait_for(started.wait(), timeout=5)
        await kernel.aclose()

        steps = await store.get_steps(result.run_id)
        assert steps[0].status is StepStatus.CLAIMED
        run = await store.get_run(result.run_id)
        assert run is not None
        assert run.status is RunStatus.RUNNING
        # It becomes reclaimable only after the lease lapses.
        assert (await store.recover_orphans(clock(), max_recoveries=10))[0] == 0
        clock.now += 31.0
        assert (await store.recover_orphans(clock(), max_recoveries=10))[0] == 1
    finally:
        release.set()
        store.close()


def test_invalid_lease_timings_are_rejected(forked_registration_context):
    """Nonsensical lease timings fail loudly at construction."""

    class TimingFlow(rx.State):
        __workflow__ = WorkflowConfig(id="lease.timing")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def work(self):
            pass

    definition = compile_workflow(TimingFlow)
    store = MemoryRunStore()
    with pytest.raises(WorkflowRuntimeError, match="Lease timings"):
        WorkflowKernel([definition], store, lease_duration=0)
    with pytest.raises(WorkflowRuntimeError, match="Lease timings"):
        WorkflowKernel(
            [definition], store, lease_duration=10.0, lease_renew_interval=10.0
        )


def test_store_without_renew_lease_is_rejected(forked_registration_context):
    """A run store that cannot renew leases is refused at construction."""

    class ProtocolFlow(rx.State):
        __workflow__ = WorkflowConfig(id="lease.protocol")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def work(self):
            pass

    class LegacyStore:
        """A store predating leases: it has no renew_lease at all."""

    definition = compile_workflow(ProtocolFlow)
    with pytest.raises(WorkflowRuntimeError, match="renew_lease"):
        WorkflowKernel([definition], LegacyStore())  # pyright: ignore[reportArgumentType]
