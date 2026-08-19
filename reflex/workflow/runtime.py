"""Workflow runtime wiring and the public ``rx.workflows`` namespace.

A ``WorkflowRuntime`` owns the compiled definitions and the kernel for one
process. ``App.add_workflow`` registers classes on the app's runtime; the
``rx.workflows`` namespace resolves the active runtime so server code can
start, cancel, and inspect runs without holding a kernel reference.
"""

from __future__ import annotations

import random
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from reflex_base.registry import RegistrationContext
from reflex_base.utils.exceptions import WorkflowDefinitionError, WorkflowRuntimeError
from reflex_base.workflow import (
    DEFAULT_LEASE_DURATION,
    DEFAULT_MAX_RECOVERIES,
    ChannelDelivery,
)

from reflex.workflow.definition import WorkflowDefinition, compile_workflow
from reflex.workflow.kernel import (
    DEFAULT_MAX_CONCURRENCY,
    DEFAULT_POLL_INTERVAL,
    WorkflowKernel,
    WorkflowObserver,
)
from reflex.workflow.records import RunStatus
from reflex.workflow.store import RunStore, resolve_store

if TYPE_CHECKING:
    from reflex.workflow.store import DeliveryDisposition

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterable, Mapping

    from reflex.state import BaseState
    from reflex.workflow.records import RunRecord, RunSnapshot, StartResult


_context_runtime: ContextVar[WorkflowRuntime | None] = ContextVar(
    "reflex_workflow_runtime", default=None
)

_default_runtime: WorkflowRuntime | None = None


class WorkflowRuntime:
    """Owns the workflow definitions and kernel for one process."""

    def __init__(
        self,
        store: RunStore | None = None,
        *,
        clock: Callable[[], float] = time.time,
        rng: Callable[[], float] = random.random,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        lease_duration: float = DEFAULT_LEASE_DURATION,
        lease_renew_interval: float | None = None,
        recovery_interval: float | None = None,
        observer: WorkflowObserver | None = None,
        max_recoveries: int = DEFAULT_MAX_RECOVERIES,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        queues: Iterable[str] | None = None,
    ):
        """Initialize the runtime.

        Args:
            store: The durable run store; defaults to a SQLite store in the
                working directory, created at startup.
            clock: Epoch-seconds time source; injectable for virtual time.
            rng: Uniform [0, 1) source used for retry jitter.
            poll_interval: Worker sleep bound between due-time checks.
            lease_duration: Seconds a claim survives without renewal before
                recovery may reclaim it.
            lease_renew_interval: Real seconds between lease renewals.
            recovery_interval: Seconds between recovery sweeps.
            observer: Receives every recorded run transition.
            max_recoveries: Infrastructure recovery budget per logical step.
            max_concurrency: How many attempts run at once.
            queues: Queues this process's worker serves; None serves all.
        """
        self._store = store
        self._clock = clock
        self._rng = rng
        self._poll_interval = poll_interval
        self._lease_duration = lease_duration
        self._lease_renew_interval = lease_renew_interval
        self._recovery_interval = recovery_interval
        self._observer = observer
        self._max_recoveries = max_recoveries
        self._max_concurrency = max_concurrency
        self._queues = tuple(queues) if queues is not None else None
        self._definitions: dict[str, WorkflowDefinition] = {}
        self._classes: dict[type, str] = {}
        self._kernel: WorkflowKernel | None = None

    def register(self, workflow_cls: type[BaseState]) -> WorkflowDefinition:
        """Compile and register a workflow class.

        Registration classifies the class as workflow-focused and detaches it
        from the session state tree. It does not publish or activate anything.

        Args:
            workflow_cls: The workflow class to register.

        Returns:
            The compiled definition.

        Raises:
            WorkflowDefinitionError: If the class is invalid or its workflow id
                is already registered by a different class.
            WorkflowRuntimeError: If the runtime has already started.
        """
        if self._kernel is not None:
            msg = "Cannot register workflows after the runtime has started."
            raise WorkflowRuntimeError(msg)
        if not isinstance(workflow_cls, type):
            msg = (
                f"Expected a workflow class, got {type(workflow_cls).__name__}. "
                "Pass the classes themselves, one argument each."
            )
            raise WorkflowDefinitionError(msg)
        existing_id = self._classes.get(workflow_cls)
        if existing_id is not None:
            return self._definitions[existing_id]
        definition = compile_workflow(workflow_cls)
        conflict = self._definitions.get(definition.workflow_id)
        if conflict is not None:
            msg = (
                f"Workflow id {definition.workflow_id!r} is already registered "
                f"by {conflict.state_cls.__name__}."
            )
            raise WorkflowDefinitionError(msg)
        self._definitions[definition.workflow_id] = definition
        self._classes[workflow_cls] = definition.workflow_id
        RegistrationContext.detach_workflow_state(workflow_cls)
        return definition

    @property
    def definitions(self) -> tuple[WorkflowDefinition, ...]:
        """The registered definitions.

        Returns:
            The compiled definitions.
        """
        return tuple(self._definitions.values())

    @property
    def kernel(self) -> WorkflowKernel:
        """The running kernel.

        Returns:
            The kernel.

        Raises:
            WorkflowRuntimeError: If the runtime has not started.
        """
        if self._kernel is None:
            msg = (
                "The workflow runtime has not started; start the app or use "
                "WorkflowTestHarness in tests."
            )
            raise WorkflowRuntimeError(msg)
        return self._kernel

    async def startup(self, *, start_worker: bool = True) -> None:
        """Build the kernel, reclaim expired claims, and start processing.

        Args:
            start_worker: Whether to launch the background worker; tests pump
                the kernel manually instead.
        """
        if self._kernel is not None:
            return
        if self._store is None:
            # Nothing was configured in code, so the environment decides:
            # hosting points REFLEX_WORKFLOW_DATABASE at managed Postgres and
            # the same app that used a local file in development scales out.
            self._store = resolve_store()
        self._kernel = WorkflowKernel(
            self._definitions.values(),
            self._store,
            clock=self._clock,
            rng=self._rng,
            poll_interval=self._poll_interval,
            lease_duration=self._lease_duration,
            lease_renew_interval=self._lease_renew_interval,
            recovery_interval=self._recovery_interval,
            observer=self._observer,
            max_recoveries=self._max_recoveries,
            max_concurrency=self._max_concurrency,
            queues=self._queues,
        )
        if start_worker:
            await self._kernel.start_worker()
        else:
            await self._kernel.recover()

    async def shutdown(self) -> None:
        """Stop the worker; an in-flight claim is reclaimed after its lease expires."""
        if self._kernel is not None:
            await self._kernel.aclose()
            self._kernel = None

    @asynccontextmanager
    async def running(self) -> AsyncIterator[WorkflowRuntime]:
        """Run the runtime for the duration of an app lifespan.

        Yields:
            The active runtime.
        """
        global _default_runtime
        await self.startup()
        previous = _default_runtime
        _default_runtime = self
        try:
            yield self
        finally:
            _default_runtime = previous
            await self.shutdown()


def get_runtime() -> WorkflowRuntime:
    """Resolve the active workflow runtime.

    Returns:
        The context-local runtime if one is active (tests), otherwise the
        process default set by the running app.

    Raises:
        WorkflowRuntimeError: If no runtime is active.
    """
    runtime = _context_runtime.get() or _default_runtime
    if runtime is None:
        msg = (
            "No workflow runtime is active. Register workflows with "
            "app.add_workflow(...) and run the app, or use WorkflowTestHarness "
            "in tests."
        )
        raise WorkflowRuntimeError(msg)
    return runtime


class WorkflowsNamespace:
    """The public ``rx.workflows`` API surface."""

    @staticmethod
    async def start(
        target: Any,
        *,
        request_key: str | None = None,
        labels: dict[str, str] | None = None,
    ) -> StartResult:
        """Start a workflow run from a manual root event.

        Args:
            target: The root event, e.g. ``MyWorkflow.start(payload)``.
            request_key: Idempotent admission key.
            labels: Server-derived indexing labels.

        Returns:
            The admission result.
        """
        return await get_runtime().kernel.start(
            target, request_key=request_key, labels=labels
        )

    @staticmethod
    async def cancel(run_id: str) -> bool:
        """Request cancellation of a run.

        Args:
            run_id: The run to cancel.

        Returns:
            True if intent was recorded on a nonterminal run.
        """
        return await get_runtime().kernel.cancel(run_id)

    @staticmethod
    async def signal(
        run_id: str,
        delivery: ChannelDelivery,
        *,
        key: str | None = None,
    ) -> DeliveryDisposition:
        """Deliver a payload to a run waiting on one of its channels.

        Args:
            run_id: The receiving run.
            delivery: The addressed payload, e.g. ``MyFlow.approved(decision)``.
            key: Sender idempotency key; a repeated key is a no-op.

        Returns:
            What the store did with the delivery.
        """
        return await get_runtime().kernel.signal(run_id, delivery, key=key)

    @staticmethod
    async def resume(run_id: str) -> bool:
        """Re-open a run suspended for operator attention.

        Use this after fixing whatever made a step's outcome uncertain: the
        frontier step gets a fresh attempt budget and runs again.

        Args:
            run_id: The run to resume.

        Returns:
            True if a suspended run was re-opened.
        """
        return await get_runtime().kernel.resume(run_id)

    @staticmethod
    async def retry(run_id: str) -> bool:
        """Re-open a failed run at the step that failed.

        Use this once the cause is fixed: the failed step runs again with a
        fresh attempt budget, and the original failure stays in history.

        Args:
            run_id: The run to retry.

        Returns:
            True if a failed run was re-opened.
        """
        return await get_runtime().kernel.retry(run_id)

    @staticmethod
    async def skip(run_id: str) -> bool:
        """Skip the step blocking a stopped run and let it continue.

        For a step that cannot succeed and is not worth failing the run over.
        It is recorded as an operator decision, and the run resumes at
        whatever comes next.

        Args:
            run_id: The run to unstick.

        Returns:
            True if a blocking step was skipped.
        """
        return await get_runtime().kernel.skip(run_id)

    @staticmethod
    async def force_complete(run_id: str, result: Any = None) -> bool:
        """End a run as completed by operator decision.

        For a run no code path will finish -- a wait nobody will answer, a
        provider that is gone. Refused while a step is claimed; cancel first
        if a worker still holds it.

        Args:
            run_id: The run to complete.
            result: Result to record on the run.

        Returns:
            True if the run was finalized.
        """
        return await get_runtime().kernel.force_finalize(
            run_id, status=RunStatus.COMPLETED, result=result
        )

    @staticmethod
    async def force_fail(run_id: str, reason: str) -> bool:
        """End a run as failed by operator decision.

        Args:
            run_id: The run to fail.
            reason: Why the operator gave up on it, recorded on the run.

        Returns:
            True if the run was finalized.
        """
        return await get_runtime().kernel.force_finalize(
            run_id, status=RunStatus.FAILED, error={"reason": reason}
        )

    @staticmethod
    async def list_runs(
        *,
        workflow_id: str | None = None,
        statuses: Iterable[RunStatus] = (),
        labels: Mapping[str, str] | None = None,
        created_before: tuple[float, str] | None = None,
        limit: int = 50,
    ) -> tuple[RunRecord, ...]:
        """List runs matching a filter, newest first.

        Args:
            workflow_id: Restrict to one workflow identity.
            statuses: Restrict to these run statuses; empty means any.
            labels: Require every one of these label values.
            created_before: Pagination cursor, the (created_at, run_id) of the
                previous page's last row.
            limit: Maximum runs to return.

        Returns:
            The matching run records.
        """
        return await get_runtime().kernel.list_runs(
            workflow_id=workflow_id,
            statuses=statuses,
            labels=labels,
            created_before=created_before,
            limit=limit,
        )

    @staticmethod
    async def get_run(run_id: str) -> RunSnapshot | None:
        """Load a read-only snapshot of a run.

        Args:
            run_id: The run identity.

        Returns:
            The snapshot, or None if the run is unknown.
        """
        return await get_runtime().kernel.get_run(run_id)


workflows = WorkflowsNamespace()
