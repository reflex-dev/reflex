"""Regressions for defects an adversarial audit reproduced."""

import asyncio
import datetime as dt

import pytest
from reflex_base.utils.exceptions import WorkflowDefinitionError
from reflex_base.workflow import Singleton, WorkflowConfig, after, fail, manual

import reflex as rx
from reflex.workflow.records import RunStatus
from reflex.workflow.runtime import WorkflowRuntime
from reflex.workflow.store import MemoryRunStore
from reflex.workflow.testing import WorkflowTestHarness


async def test_a_handler_raising_cancellederror_does_not_kill_the_worker(
    forked_registration_context,
):
    """One rude handler must not stop every later run in the process.

    asyncio marks a task cancelled whether the kernel cancelled it or the
    handler let CancelledError escape, so the kernel cannot discriminate on
    the task's own flag; it discriminates on its control signals instead.
    """

    class Rude(rx.State):
        __workflow__ = WorkflowConfig(id="audit.rude")

        @rx.event(durable=True, trigger=manual(), effect="none")
        async def go(self):
            """Let a CancelledError escape, as a handler wrapping its own work might."""
            inner = asyncio.ensure_future(asyncio.sleep(10))
            inner.cancel()
            await inner

    class Healthy(rx.State):
        __workflow__ = WorkflowConfig(id="audit.healthy")
        n: int = 0

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            """Do ordinary work."""
            self.n = 1

    runtime = WorkflowRuntime(MemoryRunStore(), poll_interval=0.02)
    runtime.register(Rude)
    runtime.register(Healthy)
    async with runtime.running():
        rude = await runtime.kernel.start(Rude.go)
        assert rude.run_id is not None
        await asyncio.sleep(0.4)
        healthy = await runtime.kernel.start(Healthy.go)
        assert healthy.run_id is not None
        snapshot = None
        for _ in range(100):
            snapshot = await runtime.kernel.get_run(healthy.run_id)
            if snapshot is not None and snapshot.status is RunStatus.COMPLETED:
                break
            await asyncio.sleep(0.02)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED

        # The rude run is treated as an ordinary failure, not a control signal.
        rude_snapshot = await runtime.kernel.get_run(rude.run_id)
        assert rude_snapshot is not None
        assert rude_snapshot.status is not RunStatus.COMPLETED


async def test_redelivery_dedupes_before_any_start_policy(
    forked_registration_context,
):
    """A provider retrying an event must not trip the policy against its own run."""

    class Paid(rx.State):
        __workflow__ = WorkflowConfig(id="audit.paid")
        invoice: str = ""

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="none",
            singleton=Singleton(key="invoice", mode="cancel"),
        )
        def on_paid(self, invoice: str):
            """Begin work for an invoice.

            Args:
                invoice: The invoice identifier.

            Returns:
                A delayed continuation.
            """
            self.invoice = invoice
            return after("1h", Paid.later)

        @rx.event(durable=True, effect="none")
        def later(self):
            """Finish later."""

    async with WorkflowTestHarness(Paid) as harness:
        first = await harness.start(Paid.on_paid("inv_1"), request_key="evt_1")
        assert first.run_id is not None
        redelivery = await harness.kernel.start(
            Paid.on_paid("inv_1"), request_key="evt_1"
        )
        assert redelivery.disposition == "deduplicated"
        assert redelivery.run_id == first.run_id

        # The run the redelivery deduplicated to must be untouched.
        snapshot = await harness.get_run(first.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING
        assert len(await harness.kernel.list_runs()) == 1


async def test_unserializable_failure_details_do_not_break_the_commit(
    forked_registration_context,
):
    """User-supplied details must not be able to break the recording commit."""

    class Detailed(rx.State):
        __workflow__ = WorkflowConfig(id="audit.detailed")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            """Fail with details that are not JSON.

            Returns:
                A failure carrying an unserializable value.
            """
            return fail("nope", details={"when": dt.datetime.now(tz=dt.UTC)})

    async with WorkflowTestHarness(Detailed) as harness:
        result = await harness.start(Detailed.go)
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.FAILED
        assert snapshot.error is not None
        assert snapshot.error["reason"] == "nope"


def test_timeout_is_rejected_on_a_synchronous_handler():
    """A thread cannot be interrupted, so timeout= would be a lie."""
    with pytest.raises(WorkflowDefinitionError, match="synchronous handler"):

        @rx.event(durable=True, trigger=manual(), effect="none", timeout="5s")
        def handler(self):
            pass


def test_timeout_is_allowed_on_an_async_handler():
    """An async handler really can be interrupted at an await point."""

    @rx.event(durable=True, trigger=manual(), effect="none", timeout="5s")
    async def handler(self):
        await asyncio.sleep(0)

    assert handler is not None
