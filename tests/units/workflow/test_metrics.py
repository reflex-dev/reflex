"""Tests for the metrics observer.

An exporter wants counters, not an event stream. These assert the numbers an
operator would actually alert on -- and that they are counters, not gauges
that reset.
"""

from reflex_base.workflow import Retry, TransientWorkflowError, WorkflowConfig, manual

import reflex as rx
from reflex.workflow.kernel import MetricsObserver
from reflex.workflow.records import HistoryEventType, RunStatus
from reflex.workflow.testing import WorkflowTestHarness

CALLS: list[int] = []


class Flaky(rx.State):
    """Fails once, then succeeds."""

    __workflow__ = WorkflowConfig(id="metrics.flaky")

    @rx.event(
        durable=True,
        trigger=manual(),
        effect="read",
        retry=Retry(max_attempts=3, initial_delay="1s", jitter="none"),
    )
    def go(self):
        """Fail the first time.

        Returns:
            Completion on the second attempt.

        Raises:
            TransientWorkflowError: On the first attempt.
        """
        CALLS.append(1)
        if len(CALLS) == 1:
            msg = "first attempt fails"
            raise TransientWorkflowError(msg)
        return rx.complete(result={"attempts": len(CALLS)})


async def test_counters_cover_a_run_with_a_retry(forked_registration_context):
    """One admitted run, two attempts, one retry, one completion."""
    CALLS.clear()
    metrics = MetricsObserver()
    async with WorkflowTestHarness(Flaky, observer=metrics) as harness:
        await harness.start(Flaky.go)
        await harness.advance("2s")

    totals = metrics.snapshot()["totals"]
    assert totals["runs_started"] == 1
    assert totals["runs_completed"] == 1
    assert totals["attempts"] == 2
    assert totals["attempts_failed"] == 1
    assert totals["retries_scheduled"] == 1
    assert "runs_failed" not in totals


async def test_counters_break_down_by_workflow(forked_registration_context):
    """A deployment alerts per workflow, not only in aggregate."""
    CALLS.clear()
    metrics = MetricsObserver()

    class Simple(rx.State):
        __workflow__ = WorkflowConfig(id="metrics.simple")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            """Succeed immediately."""

    async with WorkflowTestHarness(Flaky, Simple, observer=metrics) as harness:
        await harness.start(Simple.go)
        await harness.start(Flaky.go)
        await harness.advance("2s")

    by_workflow = metrics.snapshot()["by_workflow"]
    assert by_workflow["metrics.simple"]["runs_started"] == 1
    assert by_workflow["metrics.simple"]["attempts"] == 1
    assert by_workflow["metrics.flaky"]["attempts"] == 2
    assert "attempts_failed" not in by_workflow["metrics.simple"]


async def test_counters_only_increase(forked_registration_context):
    """A scrape-and-diff collector needs monotonic counters."""
    CALLS.clear()
    metrics = MetricsObserver()
    async with WorkflowTestHarness(Flaky, observer=metrics) as harness:
        await harness.start(Flaky.go)
        await harness.advance("2s")
        first = metrics.snapshot()["totals"]["attempts"]

        CALLS.clear()
        await harness.start(Flaky.go)
        await harness.advance("2s")
        second = metrics.snapshot()["totals"]["attempts"]

    assert second > first
    # The snapshot is a copy: reading it cannot disturb the counters.
    snapshot = metrics.snapshot()
    snapshot["totals"]["attempts"] = 0
    assert metrics.snapshot()["totals"]["attempts"] == second


async def test_a_failed_run_is_counted_as_failed(forked_registration_context):
    """The counter an on-call rotation actually pages on."""

    class Doomed(rx.State):
        __workflow__ = WorkflowConfig(id="metrics.doomed")

        @rx.event(
            durable=True, trigger=manual(), effect="read", retry=Retry(max_attempts=1)
        )
        def go(self):
            """Always fail.

            Raises:
                TransientWorkflowError: Always.
            """
            msg = "broken"
            raise TransientWorkflowError(msg)

    metrics = MetricsObserver()
    async with WorkflowTestHarness(Doomed, observer=metrics) as harness:
        await harness.start(Doomed.go)

    totals = metrics.snapshot()["totals"]
    assert totals["runs_failed"] == 1
    assert totals["attempts_failed"] == 1
    assert "runs_completed" not in totals


async def test_fanout_children_count_as_started_runs(forked_registration_context):
    """A four-run graph reports four starts, not one.

    Children are advertised as ordinary runs, so their history begins with
    admission and scheduling like anyone else's, and a dashboard's
    runs_started reconciles with its terminal counts instead of trailing
    them by the fan-out width.
    """

    class Branch(rx.State):
        __workflow__ = WorkflowConfig(id="metrics.branch")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self, lead: str):
            """Complete immediately.

            Args:
                lead: The lead identifier.

            Returns:
                Completion.
            """
            return rx.complete(result=lead)

    class Fans(rx.State):
        __workflow__ = WorkflowConfig(id="metrics.fans")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            """Fan out three branches.

            Returns:
                The parallel fan-out.
            """
            return rx.parallel(
                Branch.start("a"), Branch.start("b"), Branch.start("c"), then=Fans.done
            )

        @rx.event(durable=True, effect="none")
        def done(self, results: list):
            """Complete with the branch count.

            Args:
                results: One entry per branch.

            Returns:
                Completion.
            """
            return rx.complete(result=len(results))

    metrics = MetricsObserver()
    async with WorkflowTestHarness(Fans, Branch, observer=metrics) as harness:
        started = await harness.start(Fans.begin())
        assert started.run_id is not None
        await harness.run_until_idle()
        snapshot = await harness.get_run(started.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED

        # The durable record agrees: each child's history begins at admission.
        store = harness.kernel._store  # pyright: ignore[reportPrivateUsage]
        children = await store.list_children(started.run_id, 1)
        assert len(children) == 3
        for child in children:
            history = [event.type for event in await store.get_history(child.run_id)]
            assert history[0] is HistoryEventType.RUN_ADMITTED, history
            assert history[1] is HistoryEventType.STEP_SCHEDULED, history

    counts = metrics.snapshot()["totals"]
    assert counts["runs_started"] == 4, counts
    assert counts["runs_completed"] == 4, counts
