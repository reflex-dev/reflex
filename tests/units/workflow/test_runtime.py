"""Tests for the runtime's lifecycle.

WorkflowRuntime is what an app owns and what every `rx.workflows` call goes
through, so its lifecycle rules are load-bearing: when a kernel exists, what
happens to a double start or stop, and which mistakes are refused rather than
half-performed. All of it held under probing; none of it was written down.
"""

import pytest
from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import WorkflowConfig, manual

import reflex as rx
from reflex.workflow.runtime import WorkflowRuntime
from reflex.workflow.store import MemoryRunStore


def _flow():
    """Build a minimal registerable workflow.

    Returns:
        The workflow class.
    """

    class Simple(rx.State):
        __workflow__ = WorkflowConfig(id="runtime.simple")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            """Do nothing."""

    return Simple


async def test_the_kernel_exists_only_between_start_and_stop(
    forked_registration_context,
):
    """Reaching for the kernel too early says so instead of building one.

    A lazily created kernel would quietly give each caller its own scheduler
    against the same store.
    """
    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(_flow())

    with pytest.raises(WorkflowRuntimeError, match="not started"):
        _ = runtime.kernel

    await runtime.startup(start_worker=False)
    assert runtime.kernel is not None

    await runtime.shutdown()
    with pytest.raises(WorkflowRuntimeError, match="not started"):
        _ = runtime.kernel


async def test_starting_and_stopping_are_idempotent(forked_registration_context):
    """Lifecycle hooks fire more than once; that must not be a failure.

    An app harness, a test, and a platform supervisor can all call these, and
    a second start that built a second kernel would double every claim.
    """
    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(_flow())

    await runtime.startup(start_worker=False)
    kernel = runtime.kernel
    await runtime.startup(start_worker=False)
    assert runtime.kernel is kernel, "a second startup replaced the kernel"

    await runtime.shutdown()
    await runtime.shutdown()

    # And a runtime can be started again after being stopped.
    await runtime.startup(start_worker=False)
    assert runtime.kernel is not None
    await runtime.shutdown()


async def test_registering_after_start_is_refused(forked_registration_context):
    """A definition added after the kernel exists would never be served.

    Silently accepting it produces a workflow that is registered, absent from
    the running kernel, and impossible to start -- with nothing to explain it.
    """
    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(_flow())
    await runtime.startup(start_worker=False)
    try:
        with pytest.raises(WorkflowRuntimeError, match="after the runtime"):

            class Late(rx.State):
                __workflow__ = WorkflowConfig(id="runtime.late")

                @rx.event(durable=True, trigger=manual(), effect="none")
                def go(self):
                    """Do nothing."""

            runtime.register(Late)
    finally:
        await runtime.shutdown()


async def test_running_activates_the_facade_and_restores_it(
    forked_registration_context,
):
    """`running()` is what makes rx.workflows resolve, and it cleans up.

    A runtime that stayed active after its block would leave later code
    talking to a stopped kernel and a store nobody is draining.
    """
    flow = _flow()
    runtime = WorkflowRuntime(MemoryRunStore())
    runtime.register(flow)

    with pytest.raises(WorkflowRuntimeError, match="No workflow runtime"):
        await rx.workflows.get_run("anything")

    async with runtime.running():
        result = await rx.workflows.start(flow.go)
        assert result.run_id is not None

    with pytest.raises(WorkflowRuntimeError, match="No workflow runtime"):
        await rx.workflows.get_run(result.run_id)


def test_definitions_are_reported_once_per_class(forked_registration_context):
    """Registering the same class twice is a no-op, not a duplicate."""
    flow = _flow()
    runtime = WorkflowRuntime(MemoryRunStore())
    first = runtime.register(flow)
    second = runtime.register(flow)
    assert first is second
    assert [definition.workflow_id for definition in runtime.definitions] == [
        "runtime.simple"
    ]
