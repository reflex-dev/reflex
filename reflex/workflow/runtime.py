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
from pathlib import Path
from typing import TYPE_CHECKING, Any

from reflex_base.registry import RegistrationContext
from reflex_base.utils.exceptions import WorkflowDefinitionError, WorkflowRuntimeError
from reflex_base.workflow import DEFAULT_LEASE_DURATION

from reflex.workflow.definition import WorkflowDefinition, compile_workflow
from reflex.workflow.kernel import DEFAULT_POLL_INTERVAL, WorkflowKernel
from reflex.workflow.store import RunStore, SqliteRunStore

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from reflex.state import BaseState
    from reflex.workflow.records import RunSnapshot, StartResult

DEFAULT_DB_FILENAME = "workflow.db"

_context_runtime: ContextVar[WorkflowRuntime | None] = ContextVar(
    "reflex_workflow_runtime", default=None
)

_default_runtime: WorkflowRuntime | None = None


def _detach_from_session_registry(workflow_cls: type[BaseState]) -> None:
    """Remove a workflow class from the session state registry.

    A registered workflow class is run-scoped: it must not be instantiated per
    browser session, compiled into the client state schema, or reachable from
    frontend event dispatch. Removing it from the registration context achieves
    all three without changing the class itself.

    Args:
        workflow_cls: The workflow class being registered.
    """
    ctx = RegistrationContext.ensure_context()
    ctx.base_states.pop(workflow_cls.get_full_name(), None)
    parent = workflow_cls.get_parent_state()
    if parent is not None:
        ctx.base_state_substates.get(parent.get_full_name(), set()).discard(
            workflow_cls
        )
    for full_name, registered in list(ctx.event_handlers.items()):
        if workflow_cls in registered.states:
            del ctx.event_handlers[full_name]


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
        """
        self._store = store
        self._clock = clock
        self._rng = rng
        self._poll_interval = poll_interval
        self._lease_duration = lease_duration
        self._lease_renew_interval = lease_renew_interval
        self._recovery_interval = recovery_interval
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
        _detach_from_session_registry(workflow_cls)
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
            self._store = SqliteRunStore(Path.cwd() / DEFAULT_DB_FILENAME)
        self._kernel = WorkflowKernel(
            self._definitions.values(),
            self._store,
            clock=self._clock,
            rng=self._rng,
            poll_interval=self._poll_interval,
            lease_duration=self._lease_duration,
            lease_renew_interval=self._lease_renew_interval,
            recovery_interval=self._recovery_interval,
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
    async def get_run(run_id: str) -> RunSnapshot | None:
        """Load a read-only snapshot of a run.

        Args:
            run_id: The run identity.

        Returns:
            The snapshot, or None if the run is unknown.
        """
        return await get_runtime().kernel.get_run(run_id)


workflows = WorkflowsNamespace()
