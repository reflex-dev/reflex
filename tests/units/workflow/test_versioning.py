"""Tests for deploying new workflow code while runs are in flight."""

from reflex_base.workflow import WorkflowConfig, manual, needs_attention

import reflex as rx
from reflex.workflow.records import RunStatus, StepStatus
from reflex.workflow.store import MemoryRunStore
from reflex.workflow.testing import WorkflowTestHarness


def _flow(*, extra_field: bool = False, slow_retry: bool = False):
    """Build one shape of a workflow, standing in for one deploy.

    Args:
        extra_field: Whether this deploy declares an additional state field.
        slow_retry: Whether this deploy retunes the second step's timeout.

    Returns:
        The workflow class for this deploy.
    """

    class Deployed(rx.State):
        __workflow__ = WorkflowConfig(id="versioning.deployed")
        status: str = "pending"
        if extra_field:
            note: str = ""

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            self.status = "started"
            return rx.after("1h", Deployed.finish)

        @rx.event(
            durable=True,
            effect="read",
            timeout="90s" if slow_retry else None,
        )
        def finish(self):
            self.status = "done"

    return Deployed


async def test_added_state_field_does_not_strand_runs(forked_registration_context):
    """Adding a field is a routine deploy, not a reason to suspend live runs."""
    store = MemoryRunStore()
    first = _flow()
    async with WorkflowTestHarness(first, store=store) as harness:
        result = await harness.start(first.begin())
        assert result.run_id is not None
        run_id, resume_at = result.run_id, harness.now

    async with WorkflowTestHarness(
        _flow(extra_field=True), store=store, start_time=resume_at + 3600
    ) as harness:
        await harness.run_until_idle()
        snapshot = await harness.get_run(run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state == {"status": "done", "note": ""}


async def test_retuned_policy_does_not_strand_runs(forked_registration_context):
    """Changing a timeout or retry policy applies to future attempts only."""
    store = MemoryRunStore()
    first = _flow()
    async with WorkflowTestHarness(first, store=store) as harness:
        result = await harness.start(first.begin())
        assert result.run_id is not None
        run_id, resume_at = result.run_id, harness.now

    async with WorkflowTestHarness(
        _flow(slow_retry=True), store=store, start_time=resume_at + 3600
    ) as harness:
        await harness.run_until_idle()
        snapshot = await harness.get_run(run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED


async def test_removed_handler_suspends_with_a_precise_reason(
    forked_registration_context,
):
    """A pending step whose handler is gone cannot run, and says so."""
    store = MemoryRunStore()
    first = _flow()
    async with WorkflowTestHarness(first, store=store) as harness:
        result = await harness.start(first.begin())
        assert result.run_id is not None
        run_id, resume_at = result.run_id, harness.now

    class Truncated(rx.State):
        __workflow__ = WorkflowConfig(id="versioning.deployed")
        status: str = "pending"

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            self.status = "started"

    async with WorkflowTestHarness(
        Truncated, store=store, start_time=resume_at + 3600
    ) as harness:
        await harness.run_until_idle()
        snapshot = await harness.get_run(run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.NEEDS_ATTENTION
        assert snapshot.error is not None
        assert snapshot.error["reason"] == "unknown_handler"
        assert "finish" in snapshot.error["detail"]


async def test_unregistered_workflow_suspends(forked_registration_context):
    """A run whose workflow is no longer registered waits rather than failing."""
    store = MemoryRunStore()
    first = _flow()
    async with WorkflowTestHarness(first, store=store) as harness:
        result = await harness.start(first.begin())
        assert result.run_id is not None
        run_id, resume_at = result.run_id, harness.now

    class Unrelated(rx.State):
        __workflow__ = WorkflowConfig(id="versioning.unrelated")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            pass

    async with WorkflowTestHarness(
        Unrelated, store=store, start_time=resume_at + 3600
    ) as harness:
        await harness.run_until_idle()
        snapshot = await harness.get_run(run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.NEEDS_ATTENTION
        assert snapshot.error is not None
        assert snapshot.error["reason"] == "unknown_workflow"


async def test_resume_reopens_a_suspended_run(forked_registration_context):
    """Resuming grants the frontier step a fresh attempt budget."""
    attempts = []

    class ReviewFlow(rx.State):
        __workflow__ = WorkflowConfig(id="versioning.review")
        status: str = "pending"
        resolved: bool = False

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            attempts.append(1)
            if not self.resolved:
                return needs_attention("manual_review")
            self.status = "done"
            return None

    async with WorkflowTestHarness(ReviewFlow) as harness:
        result = await harness.start(ReviewFlow.begin())
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.NEEDS_ATTENTION

        # An operator fixes the cause, then resumes.
        run = await harness.kernel.store.get_run(result.run_id)
        assert run is not None
        run.state["resolved"] = True
        assert await harness.resume(result.run_id)

        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state["status"] == "done"
        assert snapshot.steps[0].status is StepStatus.SUCCEEDED
        assert len(attempts) == 2


async def test_resume_only_applies_to_suspended_runs(forked_registration_context):
    """A healthy or terminal run is not resumable."""

    class PlainFlow(rx.State):
        __workflow__ = WorkflowConfig(id="versioning.plain")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            pass

    async with WorkflowTestHarness(PlainFlow) as harness:
        result = await harness.start(PlainFlow.go())
        assert result.run_id is not None
        assert not await harness.resume(result.run_id)
        assert not await harness.resume("no-such-run")
