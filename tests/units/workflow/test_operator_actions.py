"""Tests for the operator actions in CONTRACT.md section 9.

Each action is legal only from the states the contract names; anything else
is a refused no-op. These assert both halves, because an action that silently
succeeds from the wrong state is how an operator corrupts a run they were
trying to rescue.
"""

from reflex_base.workflow import Retry, TransientWorkflowError, WorkflowConfig, manual

import reflex as rx
from reflex.workflow.records import RunStatus, StepStatus
from reflex.workflow.testing import WorkflowTestHarness

ATTEMPTS: list[int] = []


class Fragile(rx.State):
    """Fails until told otherwise."""

    __workflow__ = WorkflowConfig(id="ops.fragile")
    healed: bool = False

    @rx.event(
        durable=True,
        trigger=manual(),
        effect="read",
        retry=Retry(max_attempts=1),
    )
    def start(self):
        """Fail while the world is broken.

        Returns:
            Completion once healed.

        Raises:
            TransientWorkflowError: Until the operator fixes things.
        """
        ATTEMPTS.append(1)
        if not HEALED:
            msg = "downstream is down"
            raise TransientWorkflowError(msg)
        return rx.complete(result={"attempts": len(ATTEMPTS)})


HEALED = False


async def test_retry_reopens_a_failed_run(forked_registration_context):
    """A failure the operator has since fixed runs again, from that step."""
    global HEALED
    ATTEMPTS.clear()
    HEALED = False
    async with WorkflowTestHarness(Fragile) as harness:
        result = await harness.start(Fragile.start)
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.FAILED
        assert len(ATTEMPTS) == 1

        HEALED = True
        assert await harness.kernel.retry(result.run_id)
        await harness.run_until_idle()

        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert len(ATTEMPTS) == 2
        # The failure is still on the record; a retry does not rewrite history.
        history = await harness.kernel.store.get_history(result.run_id)
        assert any(event.type.value == "run_failed" for event in history)


async def test_retry_is_refused_on_a_healthy_run(forked_registration_context):
    """Retry applies to failures, not to runs that are fine."""
    global HEALED
    ATTEMPTS.clear()
    HEALED = True
    async with WorkflowTestHarness(Fragile) as harness:
        result = await harness.start(Fragile.start)
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED

        assert not await harness.kernel.retry(result.run_id)
        assert not await harness.kernel.retry("no-such-run")


async def test_force_complete_ends_a_stuck_run(forked_registration_context):
    """A wait nobody will ever answer can be ended by decision."""

    class Waiting(rx.State):
        __workflow__ = WorkflowConfig(id="ops.waiting")

        answered = rx.Signal(dict)

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self):
            """Wait forever.

            Returns:
                An unbounded wait.
            """
            return rx.wait_for(Waiting.answered, then=Waiting.done, timeout=rx.never)

        @rx.event(durable=True, effect="none")
        def done(self, payload: dict):
            """Never reached in this test.

            Args:
                payload: The delivered answer.
            """

    async with WorkflowTestHarness(Waiting) as harness:
        result = await harness.start(Waiting.start)
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING

        assert await harness.kernel.force_finalize(
            result.run_id, status=RunStatus.COMPLETED, result={"by": "operator"}
        )
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.result == {"by": "operator"}
        # The abandoned wait is tombstoned, not left dangling.
        assert all(
            step.status in (StepStatus.SUCCEEDED, StepStatus.CANCELLED)
            for step in snapshot.steps
        )


async def test_force_fail_records_the_reason(forked_registration_context):
    """Giving up on a run says who gave up and why."""

    class Stuck(rx.State):
        __workflow__ = WorkflowConfig(id="ops.stuck")

        nudged = rx.Signal(dict)

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self):
            """Wait forever.

            Returns:
                An unbounded wait.
            """
            return rx.wait_for(Stuck.nudged, then=Stuck.done, timeout=rx.never)

        @rx.event(durable=True, effect="none")
        def done(self, payload: dict):
            """Never reached.

            Args:
                payload: The delivered answer.
            """

    async with WorkflowTestHarness(Stuck) as harness:
        result = await harness.start(Stuck.start)
        assert result.run_id is not None
        assert await harness.kernel.force_finalize(
            result.run_id,
            status=RunStatus.FAILED,
            error={"reason": "vendor retired the endpoint"},
        )
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.FAILED
        assert snapshot.error is not None
        assert "vendor retired" in snapshot.error["reason"]

        # Already terminal: a second decision changes nothing.
        assert not await harness.kernel.force_finalize(
            result.run_id, status=RunStatus.COMPLETED
        )


async def test_the_public_facade_exposes_every_action(forked_registration_context):
    """rx.workflows.* is the surface user code calls, so it is what is tested.

    The kernel methods were covered while the facade wrapping them was not,
    which is how force_complete and force_fail shipped raising NameError from
    a type-checking-only import: every test called past the layer that was
    broken.
    """
    global HEALED
    ATTEMPTS.clear()
    HEALED = True
    async with WorkflowTestHarness(Fragile) as harness:
        result = await harness.start(Fragile.start)
        assert result.run_id is not None

        # Each action answers for an unknown run rather than raising.
        assert await rx.workflows.cancel("no-such-run") is False
        assert await rx.workflows.retry("no-such-run") is False
        assert await rx.workflows.resume("no-such-run") is False
        assert await rx.workflows.force_complete("no-such-run") is False
        assert await rx.workflows.force_fail("no-such-run", "gone") is False
        assert await rx.workflows.get_run("no-such-run") is None

        # And on a real run, the facade does what the kernel does.
        runs = await rx.workflows.list_runs(workflow_id="ops.fragile")
        assert [run.run_id for run in runs] == [result.run_id]
        _ = harness


async def test_force_complete_through_the_facade(forked_registration_context):
    """The documented call, exercised the way an operator would make it."""

    class Parked(rx.State):
        __workflow__ = WorkflowConfig(id="ops.parked")

        answered = rx.Signal(dict)

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self):
            """Wait forever.

            Returns:
                An unbounded wait.
            """
            return rx.wait_for(Parked.answered, then=Parked.done, timeout=rx.never)

        @rx.event(durable=True, effect="none")
        def done(self, payload: dict):
            """Never reached.

            Args:
                payload: The delivered answer.
            """

    async with WorkflowTestHarness(Parked) as harness:
        result = await harness.start(Parked.start)
        assert result.run_id is not None
        assert await rx.workflows.force_complete(result.run_id, {"by": "ops"})
        snapshot = await rx.workflows.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.result == {"by": "ops"}
        _ = harness


async def test_skip_lets_a_stuck_run_continue(forked_registration_context):
    """A step that cannot succeed need not fail the whole run.

    The vendor retired the endpoint; the notification it sent no longer
    matters; the rest of the run does. Skipping records a decision and moves
    on, which is the difference between an operator resolving a run and an
    operator abandoning it.
    """
    calls: list[str] = []

    class Pipeline(rx.State):
        __workflow__ = WorkflowConfig(id="ops.pipeline")

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="non_idempotent_write",
            retry=Retry(max_attempts=1),
        )
        def notify(self):
            """Fail in a way that suspends rather than fails the run.

            Raises:
                TransientWorkflowError: Always.
            """
            calls.append("notify")
            msg = "vendor endpoint is gone"
            raise TransientWorkflowError(msg)

    async with WorkflowTestHarness(Pipeline) as harness:
        result = await harness.start(Pipeline.notify)
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.NEEDS_ATTENTION

        assert await rx.workflows.skip(result.run_id)
        await harness.run_until_idle()

        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        # Nothing followed the skipped step, so the run is simply done.
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.steps[0].status is StepStatus.SKIPPED
        assert calls == ["notify"], "skipping re-ran the step"

        history = await harness.kernel.store.get_history(result.run_id)
        assert any(event.type.value == "step_skipped" for event in history)


async def test_skip_is_refused_on_a_healthy_run(forked_registration_context):
    """Skipping applies to a stopped run, never to one that is working."""
    global HEALED
    ATTEMPTS.clear()
    HEALED = True
    async with WorkflowTestHarness(Fragile) as harness:
        result = await harness.start(Fragile.start)
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED

        assert not await rx.workflows.skip(result.run_id)
        assert not await rx.workflows.skip("no-such-run")


async def test_retry_restores_the_chain_the_failure_tombstoned(
    forked_registration_context,
):
    """Retrying continues from the failed step, not past everything after it.

    A handler returning a list preallocates the whole chain, so a terminal
    failure tombstones the steps behind it. Retry restores exactly those --
    a CANCELLED slot in a FAILED run can only be that failure's casualty --
    so the finalizer the chain was written for still runs.
    """
    attempts: list[str] = []

    class Chain(rx.State):
        __workflow__ = WorkflowConfig(id="ops.chain")
        note: str = ""

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            """Preallocate the rest of the chain.

            Returns:
                Two successors, run in order.
            """
            return [Chain.middle(), Chain.finish()]

        @rx.event(durable=True, effect="none", retry=Retry(max_attempts=1))
        def middle(self):
            """Fail the first time an operator has not yet fixed anything.

            Raises:
                ValueError: On the first attempt.
            """
            attempts.append("middle")
            if len(attempts) == 1:
                msg = "the reason an operator would retry"
                raise ValueError(msg)

        @rx.event(durable=True, effect="none")
        def finish(self):
            """The finalizer the chain exists for.

            Returns:
                Completion.
            """
            return rx.complete(result="finished")

    async with WorkflowTestHarness(Chain) as harness:
        started = await harness.start(Chain.begin())
        assert started.run_id is not None
        await harness.run_until_idle()
        snapshot = await harness.get_run(started.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.FAILED

        assert await harness.kernel.retry(started.run_id)
        await harness.run_until_idle()

        snapshot = await harness.get_run(started.run_id)
        assert snapshot is not None
        assert snapshot.result == "finished", (
            "the retried run completed without running the finalizer the "
            f"chain preallocated: {[step.status.value for step in snapshot.steps]}"
        )


async def test_skip_restores_the_chain_the_failure_tombstoned(
    forked_registration_context,
):
    """Skipping the failed step continues at what comes next, not at nothing.

    Same chain, same failure; the operator gives up on the middle step
    instead of retrying it. The preallocated finalizer must still run --
    without restoration the run completes with the skip as its last word and
    the finalizer silently cancelled.
    """

    class SkipChain(rx.State):
        __workflow__ = WorkflowConfig(id="ops.skipchain")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            """Preallocate the rest of the chain.

            Returns:
                Two successors, run in order.
            """
            return [SkipChain.middle(), SkipChain.finish()]

        @rx.event(durable=True, effect="none", retry=Retry(max_attempts=1))
        def middle(self):
            """Fail terminally.

            Raises:
                ValueError: Always.
            """
            msg = "a vendor that retired its endpoint"
            raise ValueError(msg)

        @rx.event(durable=True, effect="none")
        def finish(self):
            """The finalizer the chain exists for.

            Returns:
                Completion.
            """
            return rx.complete(result="finished")

    async with WorkflowTestHarness(SkipChain) as harness:
        started = await harness.start(SkipChain.begin())
        assert started.run_id is not None
        await harness.run_until_idle()
        snapshot = await harness.get_run(started.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.FAILED

        assert await harness.kernel.skip(started.run_id)
        await harness.run_until_idle()

        snapshot = await harness.get_run(started.run_id)
        assert snapshot is not None
        assert snapshot.result == "finished", (
            "the skipped run completed without running the finalizer: "
            f"{[step.status.value for step in snapshot.steps]}"
        )
