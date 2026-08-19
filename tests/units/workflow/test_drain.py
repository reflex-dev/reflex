"""Tests for draining a worker, which is what makes a rolling deploy cheap.

A worker that stops the moment it is asked abandons whatever it was running
mid-attempt. Nothing is lost -- the claim is fenced and another worker picks
the step up once the lease lapses -- but every in-flight step stalls for a
lease, which on a deploy that replaces every process at once means the whole
fleet pauses. Giving running attempts a moment to commit turns that into a
handover.
"""

import asyncio
from typing import Any

import pytest
from reflex_base.workflow import WorkflowConfig, manual, parse_duration

import reflex as rx
from reflex.workflow.definition import compile_workflow
from reflex.workflow.kernel import WorkflowKernel
from reflex.workflow.records import RunQuery, RunStatus, StepStatus
from reflex.workflow.runtime import DEFAULT_DRAIN, DRAIN_ENV, configured_drain
from reflex.workflow.store import MemoryRunStore


def _flow(started: asyncio.Event, release: asyncio.Event) -> Any:
    """Build a workflow whose only step blocks until it is released.

    Each test builds its own class because each gets its own registration
    context, and its own pair of events to steer the handler with.

    Args:
        started: Set once the handler is running.
        release: Awaited by the handler before it completes.

    Returns:
        The workflow class.
    """

    class DrainFlow(rx.State):
        __workflow__ = WorkflowConfig(id="drain.flow")

        @rx.event(durable=True, trigger=manual(), effect="none")
        async def work(self):
            """Block until released, then finish.

            Returns:
                Completion.
            """
            started.set()
            await release.wait()
            return rx.complete(result="committed")

    return DrainFlow


async def test_a_drain_lets_a_running_attempt_commit(forked_registration_context):
    """The attempt in flight when the worker stops finishes durably."""
    started, release = asyncio.Event(), asyncio.Event()
    flow = _flow(started, release)
    definition = compile_workflow(flow)
    store = MemoryRunStore()
    kernel = WorkflowKernel([definition], store)
    await kernel.start(flow.work())
    await kernel.start_worker()
    await asyncio.wait_for(started.wait(), timeout=5)

    closing = asyncio.create_task(kernel.aclose(drain=5.0))
    await asyncio.sleep(0)
    release.set()
    await asyncio.wait_for(closing, timeout=10)

    snapshot = await kernel.get_run((await store.list_runs(RunQuery()))[0].run_id)
    assert snapshot is not None
    assert snapshot.status is RunStatus.COMPLETED
    assert snapshot.result == "committed"


async def test_without_a_drain_the_attempt_is_left_for_lease_recovery(
    forked_registration_context,
):
    """Closing with no budget is crash-equivalent: fenced, not resolved.

    The step keeps its claim rather than being recorded as cancelled, because
    a cancelled attempt is a decision and this is just a process leaving.
    """
    started, release = asyncio.Event(), asyncio.Event()
    flow = _flow(started, release)
    definition = compile_workflow(flow)
    store = MemoryRunStore()
    kernel = WorkflowKernel([definition], store)
    await kernel.start(flow.work())
    await kernel.start_worker()
    await asyncio.wait_for(started.wait(), timeout=5)

    await asyncio.wait_for(kernel.aclose(), timeout=10)
    release.set()

    run_id = (await store.list_runs(RunQuery()))[0].run_id
    snapshot = await kernel.get_run(run_id)
    assert snapshot is not None
    assert snapshot.status is RunStatus.RUNNING
    assert snapshot.steps[0].status is StepStatus.CLAIMED
    assert snapshot.steps[0].attempts == 0, "a stopped process spends no budget"


async def test_an_attempt_slower_than_the_drain_is_cancelled(
    forked_registration_context,
):
    """The budget is a bound, not a promise to wait for anything."""
    started, release = asyncio.Event(), asyncio.Event()
    flow = _flow(started, release)
    definition = compile_workflow(flow)
    store = MemoryRunStore()
    kernel = WorkflowKernel([definition], store)
    await kernel.start(flow.work())
    await kernel.start_worker()
    await asyncio.wait_for(started.wait(), timeout=5)

    await asyncio.wait_for(kernel.aclose(drain=0.05), timeout=10)
    release.set()

    snapshot = await kernel.get_run((await store.list_runs(RunQuery()))[0].run_id)
    assert snapshot is not None
    assert snapshot.steps[0].status is StepStatus.CLAIMED


def test_the_drain_budget_comes_from_the_environment(monkeypatch):
    """A platform's grace period is deployment config, not a code constant."""
    monkeypatch.setenv(DRAIN_ENV, "5s")
    assert configured_drain() == pytest.approx(5.0)
    monkeypatch.delenv(DRAIN_ENV)
    assert configured_drain() == pytest.approx(parse_duration(DEFAULT_DRAIN))


def test_an_unparseable_budget_does_not_stop_the_process_leaving(monkeypatch):
    """A typo in a deployment variable must not wedge a shutdown."""
    monkeypatch.setenv(DRAIN_ENV, "half an hour")
    assert configured_drain() == pytest.approx(0.0)


async def test_cancelling_one_pump_leaves_the_other_pumps_attempt_alone(
    forked_registration_context,
):
    """A pump's timeout is not another pump's lost work.

    Two callers pump one kernel; each owns the attempt it started. Cancelling
    the first must stop only its own attempt -- the second pump is
    supervising the other one, and having it yanked from outside turns one
    caller's cancellation into unrelated abandoned work.
    """
    started_one, release_one = asyncio.Event(), asyncio.Event()
    started_two, release_two = asyncio.Event(), asyncio.Event()
    flow_one = _flow(started_one, release_one)

    class SecondFlow(rx.State):
        __workflow__ = WorkflowConfig(id="drain.second")

        @rx.event(durable=True, trigger=manual(), effect="none")
        async def work(self):
            """Block until released, then finish.

            Returns:
                Completion.
            """
            started_two.set()
            await release_two.wait()
            return rx.complete(result="second survived")

    store = MemoryRunStore()
    kernel = WorkflowKernel(
        [compile_workflow(flow_one), compile_workflow(SecondFlow)],
        store,
        max_concurrency=2,
    )
    await kernel.start(flow_one.work())
    pump_one = asyncio.create_task(kernel.run_until_idle())
    await asyncio.wait_for(started_one.wait(), timeout=5)

    await kernel.start(SecondFlow.work())
    pump_two = asyncio.create_task(kernel.run_until_idle())
    await asyncio.wait_for(started_two.wait(), timeout=5)

    pump_one.cancel()
    await asyncio.gather(pump_one, return_exceptions=True)

    release_two.set()
    await asyncio.wait_for(pump_two, timeout=5)
    release_one.set()

    runs = await store.list_runs(RunQuery(limit=10))
    second = next(r for r in runs if r.workflow_id == "drain.second")
    assert second.status is RunStatus.COMPLETED, (
        "cancelling pump one killed pump two's attempt"
    )
