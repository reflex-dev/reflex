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
from reflex.workflow import runtime as runtime_module
from reflex.workflow.definition import compile_workflow
from reflex.workflow.kernel import WorkflowKernel
from reflex.workflow.records import RunStatus
from reflex.workflow.runtime import WorkflowRuntime, workflows
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


async def test_connect_starts_runs_without_becoming_a_worker(
    forked_registration_context,
):
    """A client process admits work and executes none of it.

    The process holding the business event -- a Django view, a script -- must
    be able to start a run without quietly turning into a worker, which would
    make a web request execute a workflow step and a script exit mid-attempt.
    """

    class ClientFlow(rx.State):
        __workflow__ = WorkflowConfig(id="runtime.client")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self):
            """Complete immediately.

            Returns:
                Completion.
            """
            return rx.complete(result="ran")

    store = MemoryRunStore()
    async with workflows.connect(ClientFlow, store=store) as runtime:
        handle = await workflows.submit(ClientFlow.start())
        assert handle.started
        snapshot = await handle.snapshot()
        assert snapshot is not None
        assert snapshot.status is RunStatus.PENDING
        assert runtime.kernel is not None

    served = WorkflowKernel([compile_workflow(ClientFlow)], store)
    await served.run_until_idle()
    after = await served.get_run(handle.run_id)
    assert after is not None
    assert after.status is RunStatus.COMPLETED
    assert after.result == "ran"


async def test_connect_restores_whatever_runtime_was_active(
    forked_registration_context,
):
    """A client is a scope, not a process-wide switch."""

    class ScopedFlow(rx.State):
        __workflow__ = WorkflowConfig(id="runtime.scoped")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self):
            """Complete immediately.

            Returns:
                Completion.
            """
            return rx.complete(result=None)

    async with workflows.connect(ScopedFlow, store=MemoryRunStore()):
        pass
    with pytest.raises(WorkflowRuntimeError):
        await workflows.submit(ScopedFlow.start())


class _BlippingStore(MemoryRunStore):
    """A store whose first few calls fail the way a severed connection does."""

    def __init__(self, failures: int):
        """Fail the first ``failures`` clock reads.

        Args:
            failures: How many calls to refuse before behaving.
        """
        super().__init__()
        self.failures = failures
        self.calls = 0

    async def epoch_time(self):
        """Refuse while the budget of failures lasts.

        Returns:
            The base store's answer once the blip is over.

        Raises:
            ConnectionError: While failures remain.
        """
        self.calls += 1
        if self.failures > 0:
            self.failures -= 1
            msg = "store unreachable"
            raise ConnectionError(msg)
        return await super().epoch_time()


async def test_startup_survives_a_transient_store_error(
    monkeypatch, forked_registration_context
):
    """A worker booting through a database blip comes up instead of dying.

    The chaos soak found this: a worker respawned while connections were being
    severed took the AdminShutdown straight out of startup and exited.

    Args:
        monkeypatch: Used to shorten the backoff.
        forked_registration_context: Isolates workflow registration.
    """
    monkeypatch.setattr(runtime_module, "STARTUP_BACKOFF", 0.001)
    store = _BlippingStore(failures=2)
    runtime = WorkflowRuntime(store, alerts=None)
    runtime.register(_flow())
    await runtime.startup(start_worker=True)
    assert store.failures == 0
    assert store.calls >= 3, "two refusals, then the attempt that worked"
    await runtime.shutdown()


async def test_startup_fails_fast_once_the_retry_budget_is_spent(
    monkeypatch, forked_registration_context
):
    """A store that stays unreachable still fails startup, with its real error.

    Args:
        monkeypatch: Used to shorten the backoff.
        forked_registration_context: Isolates workflow registration.
    """
    monkeypatch.setattr(runtime_module, "STARTUP_BACKOFF", 0.001)
    store = _BlippingStore(failures=99)
    runtime = WorkflowRuntime(store, alerts=None)
    runtime.register(_flow())
    with pytest.raises(ConnectionError, match="store unreachable"):
        await runtime.startup(start_worker=False)
    assert store.calls == runtime_module.STARTUP_ATTEMPTS
    assert runtime._kernel is None, "nothing half-built survives"  # pyright: ignore[reportPrivateUsage]

    store.failures = 0
    await runtime.startup(start_worker=False)
    await runtime.shutdown()
