"""Tests for the metrics observer.

An exporter wants counters, not an event stream. These assert the numbers an
operator would actually alert on -- and that they are counters, not gauges
that reset.
"""

from reflex_base.workflow import Retry, TransientWorkflowError, WorkflowConfig, manual

import reflex as rx
from reflex.workflow.kernel import MetricsObserver
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
