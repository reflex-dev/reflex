"""Tests for the workflow observer hook."""

from reflex_base.workflow import Retry, TransientWorkflowError, WorkflowConfig, manual

import reflex as rx
from reflex.workflow.kernel import LoggingObserver, WorkflowObserver
from reflex.workflow.records import HistoryEventType, RunStatus
from reflex.workflow.testing import WorkflowTestHarness


class _Collector(WorkflowObserver):
    """Records every transition it is handed."""

    def __init__(self):
        self.events: list[tuple[str, str, dict]] = []

    def on_event(self, event_type, run_id, workflow_id, data):
        """Record one transition.

        Args:
            event_type: What happened.
            run_id: The run it happened to.
            workflow_id: The workflow identity.
            data: The event payload.
        """
        self.events.append((workflow_id, event_type.value, data))


class _Exploding(WorkflowObserver):
    """An observer that always raises, to prove it cannot break a run."""

    def on_event(self, event_type, run_id, workflow_id, data):
        """Always fail.

        Args:
            event_type: What happened.
            run_id: The run it happened to.
            workflow_id: The workflow identity.
            data: The event payload.

        Raises:
            RuntimeError: Always.
        """
        msg = "instrumentation is broken"
        raise RuntimeError(msg)


def _flow():
    """Build a workflow that succeeds after one transient failure.

    Returns:
        The workflow class.
    """
    calls: list[int] = []

    class ObservedFlow(rx.State):
        __workflow__ = WorkflowConfig(id="obs.observed")
        n: int = 0

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="read",
            retry=Retry(max_attempts=3, initial_delay="1s", jitter="none"),
        )
        def go(self):
            """Do the work, failing once.

            Returns:
                Completion once the work succeeds.
            """
            calls.append(1)
            if len(calls) < 2:
                msg = "flaky"
                raise TransientWorkflowError(msg)
            self.n = 1
            return rx.complete(result={"ok": True})

    return ObservedFlow


async def test_observer_sees_the_whole_lifecycle(forked_registration_context):
    collector = _Collector()
    flow = _flow()
    async with WorkflowTestHarness(flow, observer=collector) as harness:
        result = await harness.start(flow.go)
        assert result.run_id is not None
        await harness.advance("1s")

    kinds = [kind for _, kind, _ in collector.events]
    assert HistoryEventType.RUN_ADMITTED.value in kinds
    assert HistoryEventType.ATTEMPT_FAILED.value in kinds
    assert HistoryEventType.STEP_RETRY_SCHEDULED.value in kinds
    assert HistoryEventType.RUN_COMPLETED.value in kinds


async def test_every_event_is_correlated(forked_registration_context):
    collector = _Collector()
    flow = _flow()
    async with WorkflowTestHarness(flow, observer=collector) as harness:
        await harness.start(flow.go)
        await harness.advance("1s")

    assert {workflow_id for workflow_id, _, _ in collector.events} == {"obs.observed"}
    failures = [
        data
        for _, kind, data in collector.events
        if kind == HistoryEventType.ATTEMPT_FAILED.value
    ]
    assert failures
    assert failures[0]["error"]["type"] == "TransientWorkflowError"
    assert "ordinal" in failures[0]


async def test_a_broken_observer_cannot_break_a_run(forked_registration_context):
    """Instrumentation failures are reported, never propagated."""
    flow = _flow()
    async with WorkflowTestHarness(flow, observer=_Exploding()) as harness:
        result = await harness.start(flow.go)
        assert result.run_id is not None
        await harness.advance("1s")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED


async def test_the_default_is_no_observer(forked_registration_context):
    flow = _flow()
    async with WorkflowTestHarness(flow) as harness:
        result = await harness.start(flow.go)
        assert result.run_id is not None
        await harness.advance("1s")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED


async def test_logging_observer_runs(forked_registration_context):
    """The bundled observer logs without disturbing execution."""
    flow = _flow()
    async with WorkflowTestHarness(flow, observer=LoggingObserver()) as harness:
        result = await harness.start(flow.go)
        assert result.run_id is not None
        await harness.advance("1s")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
