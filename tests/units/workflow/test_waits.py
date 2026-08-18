"""Tests for waits, signals, and human approvals."""

import pytest
from pydantic import BaseModel
from reflex_base.utils.exceptions import WorkflowDefinitionError
from reflex_base.workflow import Signal, WorkflowConfig, manual, never, wait_for

import reflex as rx
from reflex.workflow.records import RunStatus, StepStatus
from reflex.workflow.store import MemoryRunStore, SqliteRunStore
from reflex.workflow.testing import WorkflowTestHarness


class Decision(BaseModel):
    """A human decision delivered to a waiting run."""

    approved: bool
    by: str


def _review_flow():
    """Build a workflow that waits for a decision with a deadline.

    Returns:
        The workflow class.
    """

    class ReviewFlow(rx.State):
        __workflow__ = WorkflowConfig(id="waits.review")
        outcome: str = ""
        decided_by: str = ""

        review = Signal(Decision)

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self):
            return wait_for(
                ReviewFlow.review,
                then=ReviewFlow.decide,
                timeout="3d",
                on_timeout=ReviewFlow.expire,
            )

        @rx.event(durable=True, effect="none")
        def decide(self, decision: Decision):
            self.decided_by = decision.by
            self.outcome = "approved" if decision.approved else "rejected"
            return rx.complete(result={"outcome": self.outcome})

        @rx.event(durable=True, effect="none")
        def expire(self):
            self.outcome = "expired"
            return rx.fail("no_decision")

    return ReviewFlow


def test_channel_names_itself_and_validates_payloads():
    class Holder:
        review = Signal(Decision)

    assert Holder.review.name == "review"
    delivery = Holder.review({"approved": True, "by": "ada"})
    assert delivery.channel == "review"
    assert isinstance(delivery.payload, Decision)
    with pytest.raises(WorkflowDefinitionError, match="expects Decision"):
        Holder.review(42)


def test_wait_for_requires_a_timeout_branch():
    class Holder:
        review = Signal(Decision)

    with pytest.raises(WorkflowDefinitionError, match="requires on_timeout"):
        wait_for(Holder.review, then="decide", timeout="3d")
    with pytest.raises(WorkflowDefinitionError, match="never times out"):
        wait_for(Holder.review, then="decide", timeout=never, on_timeout="expire")
    with pytest.raises(WorkflowDefinitionError, match=r"rx\.Signal"):
        wait_for("review", then="decide", timeout=never)  # pyright: ignore[reportArgumentType]


async def test_wait_arms_a_blocked_slot(forked_registration_context):
    flow = _review_flow()
    async with WorkflowTestHarness(flow) as harness:
        result = await harness.start(flow.start)
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING
        assert snapshot.steps[1].status is StepStatus.BLOCKED
        assert snapshot.steps[1].wait_key == "sig:review"
        assert snapshot.steps[1].origin == "wait"


async def test_signal_resolves_the_wait(forked_registration_context):
    flow = _review_flow()
    async with WorkflowTestHarness(flow) as harness:
        result = await harness.start(flow.start)
        assert result.run_id is not None
        await harness.advance("1d")
        disposition = await harness.signal(
            result.run_id, flow.review(Decision(approved=True, by="ada"))
        )
        assert disposition == "resolved"
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state == {"outcome": "approved", "decided_by": "ada"}
        assert snapshot.result == {"outcome": "approved"}


async def test_deadline_wins_and_late_signals_are_refused(forked_registration_context):
    flow = _review_flow()
    async with WorkflowTestHarness(flow) as harness:
        result = await harness.start(flow.start)
        assert result.run_id is not None
        await harness.advance("2d")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING

        await harness.advance("2d")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.FAILED
        assert snapshot.state["outcome"] == "expired"

        # The loser of the race can no longer resolve the wait.
        assert (
            await harness.signal(
                result.run_id, flow.review(Decision(approved=True, by="late"))
            )
            == "run_terminal"
        )


async def test_signal_arriving_before_the_wait_is_not_lost(
    forked_registration_context,
):
    """A sender faster than the run must not block it forever."""
    flow = _review_flow()
    async with WorkflowTestHarness(flow) as harness:
        result = await harness.kernel.start(flow.start)
        assert result.run_id is not None
        disposition = await harness.kernel.signal(
            result.run_id, flow.review(Decision(approved=False, by="fast"))
        )
        assert disposition == "buffered"

        await harness.run_until_idle()
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state == {"outcome": "rejected", "decided_by": "fast"}


async def test_duplicate_signals_are_ignored(forked_registration_context):
    flow = _review_flow()
    async with WorkflowTestHarness(flow) as harness:
        result = await harness.kernel.start(flow.start)
        assert result.run_id is not None
        await harness.kernel.run_until_idle()
        first = await harness.kernel.signal(
            result.run_id, flow.review(Decision(approved=True, by="ada")), key="req-1"
        )
        second = await harness.kernel.signal(
            result.run_id,
            flow.review(Decision(approved=False, by="mallory")),
            key="req-1",
        )
        assert first == "resolved"
        assert second == "duplicate"
        await harness.kernel.run_until_idle()
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.state["decided_by"] == "ada"


async def test_signal_to_unknown_run(forked_registration_context):
    flow = _review_flow()
    async with WorkflowTestHarness(flow) as harness:
        assert (
            await harness.kernel.signal(
                "no-such-run", flow.review(Decision(approved=True, by="ada"))
            )
            == "unknown_run"
        )


async def test_wait_with_no_deadline_never_times_out(forked_registration_context):
    class Patient(rx.State):
        __workflow__ = WorkflowConfig(id="waits.patient")
        got: str = ""

        ping = Signal()

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self):
            return wait_for(Patient.ping, then=Patient.woken, timeout=never)

        @rx.event(durable=True, effect="none")
        def woken(self, payload: str):
            self.got = payload

    async with WorkflowTestHarness(Patient) as harness:
        result = await harness.start(Patient.start)
        assert result.run_id is not None
        await harness.advance("30d")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING
        assert snapshot.steps[1].due_at == pytest.approx(0.0)

        await harness.signal(result.run_id, Patient.ping("hello"))
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state == {"got": "hello"}


async def test_wait_survives_a_restart(forked_registration_context, tmp_path):
    """A blocked run is resolved by a signal delivered after a restart."""
    flow = _review_flow()
    db_path = tmp_path / "workflow.db"
    first = SqliteRunStore(db_path)
    async with WorkflowTestHarness(flow, store=first) as harness:
        result = await harness.start(flow.start)
        assert result.run_id is not None
        resume_at = harness.now
    first.close()

    second = SqliteRunStore(db_path)
    async with WorkflowTestHarness(
        flow, store=second, start_time=resume_at + 3600
    ) as harness:
        await harness.run_until_idle()
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING

        assert (
            await harness.signal(
                result.run_id, flow.review(Decision(approved=True, by="ada"))
            )
            == "resolved"
        )
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
    second.close()


async def test_blocked_run_does_not_spin_the_scheduler(forked_registration_context):
    """A deadline-less wait must not make the store claimable forever."""

    class Idle(rx.State):
        __workflow__ = WorkflowConfig(id="waits.idle")

        ping = Signal()

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self):
            return wait_for(Idle.ping, then=Idle.woken, timeout=never)

        @rx.event(durable=True, effect="none")
        def woken(self, payload: str):
            pass

    store = MemoryRunStore()
    async with WorkflowTestHarness(Idle, store=store) as harness:
        result = await harness.start(Idle.start)
        assert result.run_id is not None
        # Nothing is claimable and no wake-up time is scheduled, so a worker
        # sleeps rather than looping on the database.
        assert await store.claim_next(harness.now) is None
        assert await store.next_due(harness.now) is None
