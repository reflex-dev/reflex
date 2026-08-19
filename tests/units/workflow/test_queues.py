"""Tests for routing steps to named worker queues.

A queue is worker isolation: a deployment can dedicate processes to slow or
sensitive work (video encoding, a tenant, a rate-limited provider) without
those steps competing with everything else. The declaration has existed on
``@rx.event(queue=...)`` since the beginning; these tests are what make it
true.
"""

import asyncio

from reflex_base.workflow import WorkflowConfig, manual

import reflex as rx
from reflex.workflow.definition import compile_workflow
from reflex.workflow.kernel import WorkflowKernel, WorkflowObserver
from reflex.workflow.records import RunStatus
from reflex.workflow.store import MemoryRunStore

RAN_ON: dict[str, str] = {}


def _make_flow():
    """Build a two-step workflow whose steps live on different queues.

    Returns:
        The workflow class.
    """

    class Encode(rx.State):
        __workflow__ = WorkflowConfig(id="queues.encode")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def ingest(self):
            """Run on the default queue.

            Returns:
                The heavy step.
            """
            RAN_ON["ingest"] = CURRENT_WORKER[0]
            return Encode.transcode

        @rx.event(durable=True, effect="idempotent_write", queue="video")
        def transcode(self):
            """Run only on the video queue.

            Returns:
                Completion.
            """
            RAN_ON["transcode"] = CURRENT_WORKER[0]
            return rx.complete(result={"ok": True})

    return Encode


CURRENT_WORKER = [""]


class _Tagger(WorkflowObserver):
    """Observer that notes which worker executed each attempt."""

    def __init__(self, name: str):
        """Remember the worker's name.

        Args:
            name: The tag for this worker.
        """
        self.name = name

    def on_event(self, event_type, run_id, workflow_id, data):
        """Stamp the current worker before each attempt runs.

        Args:
            event_type: The recorded transition.
            run_id: The run it happened on.
            workflow_id: The workflow identity.
            data: The event payload.
        """
        from reflex.workflow.records import HistoryEventType

        if event_type is HistoryEventType.ATTEMPT_STARTED:
            CURRENT_WORKER[0] = self.name


async def _drain(kernels, run_id, timeout=5.0):
    """Run kernels until the run completes.

    Args:
        kernels: The kernels sharing the store.
        run_id: The run to wait for.
        timeout: Seconds to wait before giving up.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        snapshot = await kernels[0].get_run(run_id)
        if snapshot is not None and snapshot.status is RunStatus.COMPLETED:
            return
        await asyncio.sleep(0.02)


async def test_steps_route_to_the_worker_serving_their_queue(
    forked_registration_context,
):
    """Each step executes on a worker that serves its queue.

    The general worker must not take the video step even though it is idle and
    the step is due: taking it would put the heavy work exactly where the
    deployment said it must not run.
    """
    RAN_ON.clear()
    flow = _make_flow()
    definition = compile_workflow(flow)
    store = MemoryRunStore()
    general = WorkflowKernel(
        [definition],
        store,
        poll_interval=0.01,
        queues=("default",),
        observer=_Tagger("general"),
    )
    video = WorkflowKernel(
        [definition],
        store,
        poll_interval=0.01,
        queues=("video",),
        observer=_Tagger("video"),
    )

    result = await general.start(flow.ingest)
    assert result.run_id is not None
    await general.start_worker()
    await video.start_worker()
    try:
        await _drain([general, video], result.run_id)
    finally:
        await general.aclose()
        await video.aclose()

    assert RAN_ON == {"ingest": "general", "transcode": "video"}


async def test_a_run_waits_for_its_queues_worker(forked_registration_context):
    """Per-run order holds across queues: nothing skips ahead.

    With only the general worker running, the run stops in front of the video
    step rather than executing it somewhere it does not belong -- and the
    moment a video worker appears, it continues.
    """
    RAN_ON.clear()
    flow = _make_flow()
    definition = compile_workflow(flow)
    store = MemoryRunStore()
    general = WorkflowKernel(
        [definition],
        store,
        poll_interval=0.01,
        queues=("default",),
        observer=_Tagger("general"),
    )

    result = await general.start(flow.ingest)
    assert result.run_id is not None
    await general.start_worker()
    try:
        for _ in range(50):
            if "ingest" in RAN_ON:
                break
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.1)
        snapshot = await general.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is not RunStatus.COMPLETED
        assert "transcode" not in RAN_ON

        video = WorkflowKernel(
            [definition],
            store,
            poll_interval=0.01,
            queues=("video",),
            observer=_Tagger("video"),
        )
        await video.start_worker()
        try:
            await _drain([general, video], result.run_id)
        finally:
            await video.aclose()
    finally:
        await general.aclose()

    snapshot = await general.get_run(result.run_id)
    assert snapshot is not None
    assert snapshot.status is RunStatus.COMPLETED
    assert RAN_ON["transcode"] == "video"


async def test_an_unrestricted_worker_serves_every_queue(
    forked_registration_context,
):
    """The default deployment shape stays a single process serving it all."""
    RAN_ON.clear()
    flow = _make_flow()
    definition = compile_workflow(flow)
    store = MemoryRunStore()
    worker = WorkflowKernel(
        [definition], store, poll_interval=0.01, observer=_Tagger("only")
    )

    result = await worker.start(flow.ingest)
    assert result.run_id is not None
    await worker.start_worker()
    try:
        await _drain([worker], result.run_id)
    finally:
        await worker.aclose()

    assert RAN_ON == {"ingest": "only", "transcode": "only"}
