"""Tests for deploying new workflow code while runs are in flight."""

from reflex_base.workflow import (
    Signal,
    WorkflowConfig,
    manual,
    needs_attention,
    wait_for,
)

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
        async def finish(self):
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
    resolved = []

    class ReviewFlow(rx.State):
        __workflow__ = WorkflowConfig(id="versioning.review")
        status: str = "pending"

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            attempts.append(1)
            if not resolved:
                return needs_attention("manual_review")
            self.status = "done"
            return None

    async with WorkflowTestHarness(ReviewFlow) as harness:
        result = await harness.start(ReviewFlow.begin())
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.NEEDS_ATTENTION

        # An operator fixes the cause outside the run, then resumes it.
        resolved.append(True)
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


async def test_a_newly_required_parameter_suspends(forked_registration_context):
    """Adding a parameter with no default is a redeploy problem, not a crash.

    The pending step recorded no arguments, so the new signature cannot bind.
    Failing the run buries a deploy mistake in a TypeError from inside the
    handler; suspending names what to ship and leaves the run resumable.
    """
    store = MemoryRunStore()
    first = _flow()
    async with WorkflowTestHarness(first, store=store) as harness:
        result = await harness.start(first.begin())
        assert result.run_id is not None
        run_id, resume_at = result.run_id, harness.now

    class Widened(rx.State):
        __workflow__ = WorkflowConfig(id="versioning.deployed")
        status: str = "pending"

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            """Start the run.

            Returns:
                The next step.
            """
            self.status = "started"
            return rx.after("1h", Widened.finish)

        @rx.event(durable=True, effect="read")
        async def finish(self, ticket: str):
            """Finish, now demanding an argument nothing recorded.

            Args:
                ticket: The newly required argument.
            """
            self.status = ticket

    async with WorkflowTestHarness(
        Widened, store=store, start_time=resume_at + 3600
    ) as harness:
        await harness.run_until_idle()
        snapshot = await harness.get_run(run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.NEEDS_ATTENTION
        assert snapshot.error is not None
        assert snapshot.error["reason"] == "incompatible_payload"
        assert "ticket" in snapshot.error["detail"]


async def test_a_new_parameter_with_a_default_is_compatible(
    forked_registration_context,
):
    """The supported way to widen a handler still deploys without a suspension."""
    store = MemoryRunStore()
    first = _flow()
    async with WorkflowTestHarness(first, store=store) as harness:
        result = await harness.start(first.begin())
        assert result.run_id is not None
        run_id, resume_at = result.run_id, harness.now

    class Defaulted(rx.State):
        __workflow__ = WorkflowConfig(id="versioning.deployed")
        status: str = "pending"

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            """Start the run.

            Returns:
                The next step.
            """
            self.status = "started"
            return rx.after("1h", Defaulted.finish)

        @rx.event(durable=True, effect="read")
        async def finish(self, ticket: str = "unset"):
            """Finish, with a default the recorded payload can leave alone.

            Args:
                ticket: Optional argument.

            Returns:
                Completion.
            """
            self.status = ticket
            return rx.complete(result=ticket)

    async with WorkflowTestHarness(
        Defaulted, store=store, start_time=resume_at + 3600
    ) as harness:
        await harness.run_until_idle()
        snapshot = await harness.get_run(run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.result == "unset"


async def test_a_waiting_run_whose_continuation_is_gone_suspends(
    forked_registration_context,
):
    """A wait reaches its handler by a different path, and it is gated too.

    The compatibility gate is easy to reason about for a plain successor: the
    slot names a handler and the claim checks it. A wait's continuation is
    reached with an injected payload, and a join's with injected results, so
    "the gate applies here as well" is a separate fact rather than the same
    one. A worker that crashed on a resolved wait instead of suspending the
    run would take out the process for every other run it was serving.

    Args:
        forked_registration_context: Isolates workflow registration.
    """
    store = MemoryRunStore()

    class Reviewed(rx.State):
        __workflow__ = WorkflowConfig(id="versioning.reviewed")

        review = Signal(dict)

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            """Wait for a review.

            Returns:
                The wait.
            """
            return wait_for(
                Reviewed.review,
                then=Reviewed.decide,
                timeout="3d",
                on_timeout=Reviewed.expire,
            )

        @rx.event(durable=True, effect="none")
        def decide(self, decision: dict):
            """Record the decision.

            Args:
                decision: The delivered payload.

            Returns:
                Completion.
            """
            return rx.complete(result=decision)

        @rx.event(durable=True, effect="none")
        def expire(self):
            """Give up.

            Returns:
                Failure.
            """
            return rx.fail("no_decision")

    async with WorkflowTestHarness(Reviewed, store=store) as harness:
        started = await harness.start(Reviewed.begin())
        assert started.run_id is not None
        run_id, resume_at = started.run_id, harness.now

    class Truncated(rx.State):
        __workflow__ = WorkflowConfig(id="versioning.reviewed")

        review = Signal(dict)

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            """Wait for a review.

            Returns:
                The wait.
            """
            return wait_for(
                Truncated.review,
                then=Truncated.expire,
                timeout="3d",
                on_timeout=Truncated.expire,
            )

        @rx.event(durable=True, effect="none")
        def expire(self):
            """Give up.

            Returns:
                Failure.
            """
            return rx.fail("no_decision")

    async with WorkflowTestHarness(
        Truncated, store=store, start_time=resume_at + 60
    ) as harness:
        assert (
            await harness.signal(run_id, Truncated.review({"ok": True})) == "resolved"
        )
        snapshot = await harness.get_run(run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.NEEDS_ATTENTION, snapshot.status
        assert snapshot.error is not None
        assert snapshot.error["reason"] == "unknown_handler"
        assert "decide" in snapshot.error["detail"]


async def test_a_join_whose_continuation_is_gone_suspends(
    forked_registration_context,
):
    """The same fact for a fan-out's results slot.

    The branch soaks so the join is still open across the redeploy; a branch
    that finished immediately would resolve the join under the old code and
    prove nothing about the new.

    Args:
        forked_registration_context: Isolates workflow registration.
    """
    store = MemoryRunStore()

    class Branch(rx.State):
        __workflow__ = WorkflowConfig(id="versioning.branch")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            """Soak, then finish.

            Returns:
                A deferral.
            """
            return rx.after("1h", Branch.done)

        @rx.event(durable=True, effect="none")
        def done(self):
            """Finish.

            Returns:
                Completion.
            """
            return rx.complete(result={"done": True})

    class Fanned(rx.State):
        __workflow__ = WorkflowConfig(id="versioning.fanned")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            """Fan out to one branch.

            Returns:
                The fan-out.
            """
            return rx.parallel(Branch.go(), then=Fanned.gather)

        @rx.event(durable=True, effect="none")
        def gather(self, results: list):
            """Collect the branch results.

            Args:
                results: One entry per branch.

            Returns:
                Completion.
            """
            return rx.complete(result={"branches": len(results)})

    async with WorkflowTestHarness(Fanned, Branch, store=store) as harness:
        started = await harness.start(Fanned.begin())
        assert started.run_id is not None
        run_id, resume_at = started.run_id, harness.now
        snapshot = await harness.get_run(run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING, "the join is open on the branch"

    class Truncated(rx.State):
        __workflow__ = WorkflowConfig(id="versioning.fanned")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            """Fan out to one branch.

            Returns:
                The fan-out.
            """
            return rx.parallel(Branch.go(), then=Truncated.begin)

    async with WorkflowTestHarness(
        Truncated, Branch, store=store, start_time=resume_at
    ) as harness:
        await harness.advance("2h")
        snapshot = await harness.get_run(run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.NEEDS_ATTENTION, snapshot.status
        assert snapshot.error is not None
        assert snapshot.error["reason"] == "unknown_handler"
        assert "gather" in snapshot.error["detail"]
