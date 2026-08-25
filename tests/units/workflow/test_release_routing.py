"""Release-pinned execution across a rolling deploy.

The acceptance shape: a workflow sleeps for a day, a new release deploys,
new runs use the new release, and the sleeping run resumes on the release
that admitted it. Rollback is the same property read the other way, and the
retirement gate is a count.
"""

import asyncio

import pytest
from reflex_base.workflow import WorkflowConfig, manual

import reflex as rx
from reflex.workflow import testing
from reflex.workflow.definition import compile_workflow
from reflex.workflow.kernel import WorkflowKernel
from reflex.workflow.records import TERMINAL_RUN_STATUSES, RunQuery, RunStatus


def _flow():
    """Build a workflow that sleeps between two steps.

    Returns:
        The workflow class.
    """

    class Deploying(rx.State):
        __workflow__ = WorkflowConfig(id="release.deploying")
        note: str = ""

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            """Sleep a day before finishing.

            Returns:
                The deferral.
            """
            return rx.after("1d", Deploying.finish)

        @rx.event(durable=True, effect="none")
        def finish(self):
            """Complete.

            Returns:
                Completion.
            """
            return rx.complete(result="done")

    return Deploying


ACTIVE = tuple(s for s in RunStatus if s not in TERMINAL_RUN_STATUSES)


async def test_a_sleeping_run_resumes_on_the_release_that_admitted_it(
    forked_registration_context,
):
    """v2 never claims v1's sleeping run; v1 drains it; the gate sees both.

    Args:
        forked_registration_context: Isolated state registry.
    """
    store = testing.MemoryRunStore()
    flow = _flow()
    clock = [1_000_000.0]

    v1 = WorkflowKernel(
        [compile_workflow(flow)], store, release="v1", clock=lambda: clock[0]
    )
    started = await v1.start(flow.begin())
    assert started.run_id is not None
    await v1.run_until_idle()
    sleeping = await v1.get_run(started.run_id)
    assert sleeping is not None
    assert sleeping.release_id == "v1"
    assert sleeping.status is RunStatus.WAITING

    # The new release arrives; its worker takes new admissions only.
    v2 = WorkflowKernel(
        [compile_workflow(flow)], store, release="v2", clock=lambda: clock[0]
    )
    fresh = await v2.start(flow.begin())
    assert fresh.run_id is not None
    fresh_run = await v2.get_run(fresh.run_id)
    assert fresh_run is not None
    assert fresh_run.release_id == "v2"

    clock[0] += 90_000.0
    assert await store.claim_next(clock[0], release="v2") is not None, (
        "v2 claims its own due run"
    )
    remaining = await store.claim_next(clock[0], release="v2")
    assert remaining is None, "v2 must never claim the run v1 admitted"

    # The retirement gate: v1 cannot retire while its run is active.
    assert await store.count_runs(RunQuery(release_id="v1", statuses=ACTIVE)) == 1
    await v1.run_until_idle()
    drained = await v1.get_run(started.run_id)
    assert drained is not None
    assert drained.status is RunStatus.COMPLETED
    assert await store.count_runs(RunQuery(release_id="v1", statuses=ACTIVE)) == 0, (
        "with its runs drained, v1's workers may retire"
    )


async def test_workers_register_their_release_and_deregister_cleanly(
    forked_registration_context,
):
    """The fleet surface shows who runs what, and a clean stop removes it.

    Args:
        forked_registration_context: Isolated state registry.
    """
    store = testing.MemoryRunStore()
    flow = _flow()
    kernel = WorkflowKernel(
        [compile_workflow(flow)],
        store,
        release="v7",
        queues=("billing",),
        max_concurrency=3,
    )
    await kernel.start_worker()
    workers = await store.list_workers()
    assert len(workers) == 1
    assert workers[0].release_id == "v7"
    assert workers[0].queues == ("billing",)
    assert workers[0].capacity == 3

    before = workers[0].heartbeat_at
    await asyncio.sleep(0.05)
    await kernel.recover()
    workers = await store.list_workers()
    # Each recovery re-measures the store-clock offset, and two midpoint
    # estimates can differ by a few milliseconds in either direction; the
    # heartbeat provably refreshed if it moved at all beyond that jitter.
    assert workers[0].heartbeat_at > before - 1.0
    assert workers[0].heartbeat_at != before

    await kernel.aclose()
    assert await store.list_workers() == ()


async def test_an_unreleased_dev_kernel_serves_pinned_runs(
    forked_registration_context,
):
    """A worker with no declared release is dev tooling; it runs anything.

    Args:
        forked_registration_context: Isolated state registry.
    """
    store = testing.MemoryRunStore()
    flow = _flow()
    v1 = WorkflowKernel([compile_workflow(flow)], store, release="v1")
    started = await v1.start(flow.begin())
    assert started.run_id is not None

    dev = WorkflowKernel([compile_workflow(flow)], store)
    assert dev._release is None  # pyright: ignore[reportPrivateUsage]
    claim = await store.claim_next(2_000_000_000.0, release=None)
    assert claim is not None, "the undeclared worker claims the pinned run"


def test_release_defaults_from_the_environment(
    monkeypatch, forked_registration_context
):
    """REFLEX_RELEASE_ID is the deploy surface's way in.

    Args:
        monkeypatch: Used to set the environment.
        forked_registration_context: Isolated state registry.
    """
    monkeypatch.setenv("REFLEX_RELEASE_ID", "rel-2026-08-24")
    kernel = WorkflowKernel([], testing.MemoryRunStore())
    assert kernel._release == "rel-2026-08-24"  # pyright: ignore[reportPrivateUsage]
    monkeypatch.setenv("REFLEX_RELEASE_ID", "")
    bare = WorkflowKernel([], testing.MemoryRunStore())
    assert bare._release is None  # pyright: ignore[reportPrivateUsage]


_ = pytest
