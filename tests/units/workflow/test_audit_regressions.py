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
            return fail("nope", details={"when": dt.datetime.now(tz=dt.timezone.utc)})

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


def test_an_unregistered_workflow_is_not_browser_reachable(
    forked_registration_context,
):
    """Forgetting app.add_workflow() must not expose durable handlers."""
    from reflex_base.registry import RegistrationContext

    from reflex.state import State

    class Forgotten(rx.State):
        __workflow__ = WorkflowConfig(id="audit.forgotten")
        amount: int = 0

        @rx.event(durable=True, trigger=manual(), effect="non_idempotent_write")
        def charge(self):
            """Move real money."""

    context = RegistrationContext.get()
    assert Forgotten not in State.get_substates()
    assert Forgotten.get_full_name() not in context.base_states
    assert not [
        name
        for name, registered in context.event_handlers.items()
        if Forgotten in registered.states
    ]


async def test_signal_after_deadline_is_refused(forked_registration_context):
    """Once the deadline wins, a late signal is refused rather than buffered."""
    from reflex_base.workflow import Signal, wait_for

    class Expiring(rx.State):
        __workflow__ = WorkflowConfig(id="audit.expiring")
        outcome: str = ""

        ping = Signal()

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            """Wait briefly for a signal.

            Returns:
                The wait.
            """
            return wait_for(
                Expiring.ping,
                then=Expiring.woke,
                timeout="1h",
                on_timeout=Expiring.late,
            )

        @rx.event(durable=True, effect="none")
        def woke(self, payload: str):
            """Resume on the signal.

            Args:
                payload: The delivered payload.
            """
            self.outcome = "signalled"

        @rx.event(durable=True, effect="none")
        def late(self):
            """Give up after the deadline."""
            self.outcome = "expired"

    async with WorkflowTestHarness(Expiring) as harness:
        result = await harness.kernel.start(Expiring.begin)
        assert result.run_id is not None
        await harness.kernel.run_until_idle()

        # The deadline has fallen due but no worker has claimed it yet.
        harness._clock.now += 3601
        assert (
            await harness.kernel.signal(result.run_id, Expiring.ping("late"))
            == "expired"
        )

        await harness.kernel.run_until_idle()
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.state["outcome"] == "expired"


async def test_a_child_failed_by_recovery_reports_to_its_join(
    forked_registration_context,
):
    """A child that exhausts its recovery budget must not hang its parent."""

    class Branch(rx.State):
        __workflow__ = WorkflowConfig(id="audit.branch")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self, lead: str):
            """Finish immediately.

            Args:
                lead: The lead identifier.

            Returns:
                Completion.
            """
            return rx.complete(result={"ok": True})

    class Parent(rx.State):
        __workflow__ = WorkflowConfig(id="audit.parent")
        outcomes: list[str] = []

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self, lead: str):
            """Fan out to two branches.

            Args:
                lead: The lead identifier.

            Returns:
                The fan-out.
            """
            return rx.parallel(Branch.go(lead), Branch.go(lead), then=Parent.join)

        @rx.event(durable=True, effect="none")
        def join(self, results: list):
            """Record every branch outcome.

            Args:
                results: One entry per branch.

            Returns:
                Completion.
            """
            self.outcomes = sorted(entry["status"] for entry in results)
            return rx.complete(result={"branches": len(results)})

    async with WorkflowTestHarness(Parent, Branch, max_recoveries=0) as harness:
        store = harness.kernel.store
        result = await harness.kernel.start(Parent.begin("lead_1"))
        assert result.run_id is not None
        # Run only the parent's root so the children exist but have not run.
        assert await harness.kernel._tick()

        children = [
            run
            for run in await harness.kernel.list_runs()
            if run.parent_run_id == result.run_id
        ]
        assert len(children) == 2

        # Claim one branch, then abandon it past its recovery budget, as a
        # crash loop would. max_recoveries=0 exhausts it on the first sweep.
        claim = await store.claim_next(harness.now, lease_duration=1.0)
        assert claim is not None
        doomed_id = claim.run.run_id
        harness._clock.now += 2
        # recover() is what tells a parent's join about a child it failed.
        assert await harness.kernel.recover() == 1

        await harness.kernel.recover()
        await harness.kernel.run_until_idle()

        failed = await store.get_run(doomed_id)
        assert failed is not None
        assert failed.status is RunStatus.FAILED

        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert "FAILED" in snapshot.state["outcomes"]


def test_fanning_out_to_your_own_class_is_rejected(forked_registration_context):
    """A same-class branch would silently get empty state."""
    import importlib.util
    import sys
    import tempfile
    import uuid as uuid_module
    from pathlib import Path

    source = """
import reflex as rx
from reflex_base.workflow import WorkflowConfig, manual, parallel


class SelfFanOut(rx.State):
    __workflow__ = WorkflowConfig(id="audit.self_fanout")
    lead_id: str = ""

    @rx.event(durable=True, trigger=manual(), effect="none")
    def begin(self, lead_id: str):
        self.lead_id = lead_id
        return parallel(SelfFanOut.enrich, SelfFanOut.score, then=SelfFanOut.join)

    @rx.event(durable=True, effect="none")
    def enrich(self):
        pass

    @rx.event(durable=True, effect="none")
    def score(self):
        pass

    @rx.event(durable=True, effect="none")
    def join(self, results: list):
        pass
"""
    name = f"wf_selffan_{uuid_module.uuid4().hex}"
    path = Path(tempfile.gettempdir()) / f"{name}.py"
    path.write_text(source)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

    from reflex.workflow.definition import compile_workflow

    with pytest.raises(WorkflowDefinitionError, match="its own class"):
        compile_workflow(module.SelfFanOut)


async def test_a_branch_must_be_a_manual_root(forked_registration_context):
    """Fan-out must not reach a root that only a provider may start."""
    from reflex_base.workflow import hmac_signature, parallel, webhook

    class Hooked(rx.State):
        __workflow__ = WorkflowConfig(id="audit.hooked")

        @rx.event(
            durable=True,
            effect="none",
            trigger=webhook(
                "audit.topic",
                verify=hmac_signature(secret_env="S", header="X-Sig"),
            ),
        )
        def on_event(self):
            """Only a verified provider may start this."""

    class Driver(rx.State):
        __workflow__ = WorkflowConfig(id="audit.driver")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            """Try to fan out to a webhook-only root.

            Returns:
                The fan-out.
            """
            return parallel(Hooked.on_event, then=Driver.join)

        @rx.event(durable=True, effect="none")
        def join(self, results: list):
            """Never reached.

            Args:
                results: Branch outcomes.
            """

    async with WorkflowTestHarness(Driver, Hooked) as harness:
        result = await harness.start(Driver.begin)
        assert result.run_id is not None
        # The branch is resolved while the parent's step runs, so the gate
        # surfaces as a failed parent rather than a raise at start().
        await harness.advance("1s")
        await harness.advance("2s")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.FAILED
        assert snapshot.error is not None
        assert "manual root" in snapshot.error["message"]
        # No child run was created for the webhook-only root.
        assert all(
            run.workflow_id != "audit.hooked"
            for run in await harness.kernel.list_runs()
        )
