"""The in-process durable workflow kernel.

The kernel admits runs, claims the due frontier step of each run's mailbox,
executes the durable handler against a hydrated run-state instance, and
atomically commits the state patch together with the successor slots the
handler returned. Retries, timeouts, lifecycle hooks, cancellation drain,
claim-lease renewal, and crash recovery are decided here and made durable by
the store.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
import time
import traceback
import uuid
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter
from reflex_base.event.processor.base_state_processor import _transform_event_payload
from reflex_base.utils import console
from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import (
    DEFAULT_LEASE_DURATION,
    DEFAULT_MAX_RECOVERIES,
    After,
    CompleteRun,
    FailRun,
    NeedsAttention,
    ScheduleTrigger,
    parse_duration,
)

from reflex.event import EventHandler, EventSpec
from reflex.workflow.cron import CronSchedule
from reflex.workflow.records import (
    TERMINAL_STEP_STATUSES,
    HistoryEventType,
    RunQuery,
    RunRecord,
    RunSnapshot,
    RunStatus,
    StartResult,
    StepRecord,
    StepStatus,
)
from reflex.workflow.serde import to_run_data
from reflex.workflow.store import Claim, RunStore, StaleClaimError, StepCompletion

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from reflex.state import BaseState
    from reflex.workflow.definition import HandlerDefinition, WorkflowDefinition

DEFAULT_POLL_INTERVAL = 0.25

LEASE_RENEW_FRACTION = 1 / 3

RECOVERY_INTERVAL_FRACTION = 1 / 2

MAX_SCHEDULE_CATCHUP = 10


def _error_payload(error: BaseException) -> dict[str, Any]:
    """Build a JSON-compatible error payload from an exception.

    Args:
        error: The exception to record.

    Returns:
        The error payload.
    """
    return {
        "type": type(error).__name__,
        "message": str(error),
        "traceback": "".join(
            traceback.format_exception(type(error), error, error.__traceback__)
        ),
    }


class _SuccessorSpec:
    """A resolved successor slot to allocate at commit.

    Attributes:
        handler_id: The successor handler id.
        args: JSON-compatible payload for the successor.
        delay: Seconds to wait before the slot becomes due.
        origin: How the slot was requested.
    """

    __slots__ = ("args", "delay", "handler_id", "origin")

    def __init__(
        self,
        handler_id: str,
        args: dict[str, Any],
        delay: float = 0.0,
        origin: str = "chain",
    ):
        """Initialize the successor spec.

        Args:
            handler_id: The successor handler id.
            args: JSON-compatible payload for the successor.
            delay: Seconds to wait before the slot becomes due.
            origin: How the slot was requested.
        """
        self.handler_id = handler_id
        self.args = args
        self.delay = delay
        self.origin = origin


class _Lease:
    """The live claim lease of one in-flight attempt.

    Attributes:
        claim: The claim being kept alive.
        attempt: The task running the handler, once created.
        renewer: The background task extending the lease.
        lost: Whether the store reported the claim was fenced.
    """

    __slots__ = ("attempt", "claim", "lost", "renewer")

    def __init__(self, claim: Claim):
        """Initialize the lease.

        Args:
            claim: The claim being kept alive.
        """
        self.claim = claim
        self.attempt: asyncio.Task | None = None
        self.renewer: asyncio.Task | None = None
        self.lost = False


class WorkflowKernel:
    """Executes durable workflow runs against a run store."""

    def __init__(
        self,
        definitions: Iterable[WorkflowDefinition],
        store: RunStore,
        *,
        clock: Callable[[], float] = time.time,
        rng: Callable[[], float] = random.random,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        max_recoveries: int = DEFAULT_MAX_RECOVERIES,
        lease_duration: float = DEFAULT_LEASE_DURATION,
        lease_renew_interval: float | None = None,
        recovery_interval: float | None = None,
    ):
        """Initialize the kernel.

        Args:
            definitions: Compiled workflow definitions to serve.
            store: The durable run store.
            clock: Epoch-seconds time source; injectable for virtual time.
            rng: Uniform [0, 1) source used for retry jitter.
            poll_interval: Worker sleep bound between due-time checks.
            max_recoveries: Infrastructure recovery budget per logical step.
            lease_duration: Seconds a claim survives without renewal before
                recovery may reclaim it.
            lease_renew_interval: Real seconds between lease renewals; defaults
                to a third of ``lease_duration``.
            recovery_interval: Seconds between recovery sweeps in the
                background worker; defaults to half of ``lease_duration``.

        Raises:
            WorkflowRuntimeError: If the store cannot renew leases, or the
                lease timings are inconsistent.
        """
        self._definitions: dict[str, WorkflowDefinition] = {
            defn.workflow_id: defn for defn in definitions
        }
        self._definitions_by_cls: dict[type, WorkflowDefinition] = {
            defn.state_cls: defn for defn in self._definitions.values()
        }
        self._store = store
        self._clock = clock
        self._rng = rng
        self._poll_interval = poll_interval
        self._max_recoveries = max_recoveries
        if not hasattr(store, "renew_lease"):
            msg = (
                f"{type(store).__name__} does not implement renew_lease; a run "
                "store must renew claim leases or recovery will reclaim live "
                "claims and execute steps twice."
            )
            raise WorkflowRuntimeError(msg)
        renew = (
            lease_renew_interval
            if lease_renew_interval is not None
            else lease_duration * LEASE_RENEW_FRACTION
        )
        recovery = (
            recovery_interval
            if recovery_interval is not None
            else lease_duration * RECOVERY_INTERVAL_FRACTION
        )
        if lease_duration <= 0 or not 0 < renew < lease_duration or recovery <= 0:
            msg = (
                "Lease timings must satisfy 0 < lease_renew_interval < "
                "lease_duration and recovery_interval > 0, got "
                f"{renew} / {lease_duration} / {recovery}."
            )
            raise WorkflowRuntimeError(msg)
        self._lease_duration = lease_duration
        self._lease_renew_interval = renew
        self._recovery_interval = recovery
        self._schedules = [
            (defn, handler, CronSchedule(handler.trigger.cron))
            for defn in self._definitions.values()
            for handler in (defn.handlers[hid] for hid in defn.roots)
            if isinstance(handler.trigger, ScheduleTrigger)
        ]
        # Seeded at construction so a freshly started process never backfills
        # occurrences from before it existed.
        self._schedule_cursor: dict[str, float] = {
            f"{defn.workflow_id}:{handler.id}": clock()
            for defn, handler, _ in self._schedules
        }
        self._field_adapters: dict[tuple[str, str], TypeAdapter] = {}
        self._inflight: dict[str, asyncio.Task] = {}
        self._leases: dict[str, _Lease] = {}
        self._next_recovery_at = 0.0
        self._worker_id = uuid.uuid4().hex
        self._wakeup = asyncio.Event()
        self._worker: asyncio.Task | None = None

    @property
    def store(self) -> RunStore:
        """The kernel's durable run store.

        Returns:
            The store.
        """
        return self._store

    def _resolve_target(
        self, target: Any
    ) -> tuple[WorkflowDefinition, HandlerDefinition, dict[str, Any]]:
        """Resolve a start target into a definition, handler, and payload.

        Args:
            target: An ``EventSpec`` from calling a class-level handler, or a
                class-level ``EventHandler`` reference for no-arg handlers.

        Returns:
            The workflow definition, handler definition, and decoded payload.

        Raises:
            WorkflowRuntimeError: If the target does not reference a handler on
                a registered workflow class, or its args are not literal values.
        """
        if isinstance(target, EventSpec):
            handler = target.handler
            args = {}
            for name_var, value_var in target.args:
                try:
                    value = value_var._var_value  # pyright: ignore[reportAttributeAccessIssue]
                except (AttributeError, NotImplementedError):
                    msg = (
                        "Workflow event arguments must be literal values, "
                        f"got {value_var!r} for {name_var._js_expr!r}."
                    )
                    raise WorkflowRuntimeError(msg) from None
                args[name_var._js_expr] = value
        elif isinstance(target, EventHandler):
            handler = target
            args = {}
        else:
            msg = (
                "Expected a workflow event like MyWorkflow.my_handler or "
                f"MyWorkflow.my_handler(args), got {target!r}."
            )
            raise WorkflowRuntimeError(msg)
        state_cls = handler.state
        defn = (
            self._definitions_by_cls.get(state_cls) if state_cls is not None else None
        )
        if defn is None:
            msg = (
                f"{state_cls.__name__ if state_cls is not None else target!r} is "
                "not a registered workflow; call app.add_workflow(...) first."
            )
            raise WorkflowRuntimeError(msg)
        handler_name = handler.fn.__name__
        handler_id = defn.handler_ids_by_name.get(handler_name)
        if handler_id is None:
            msg = f"{handler_name!r} is not a durable handler on {defn.workflow_id!r}."
            raise WorkflowRuntimeError(msg)
        return defn, defn.handlers[handler_id], self._normalize_payload(args)

    @staticmethod
    def _normalize_payload(args: dict[str, Any]) -> dict[str, Any]:
        """Normalize a payload to JSON-compatible values.

        Args:
            args: The raw payload values.

        Returns:
            The normalized payload.

        Raises:
            WorkflowRuntimeError: If a value is not serializable.
        """
        try:
            return to_run_data(args)
        except (TypeError, ValueError) as err:
            msg = f"Workflow event payload is not serializable: {err}"
            raise WorkflowRuntimeError(msg) from None

    async def start(
        self,
        target: Any,
        *,
        request_key: str | None = None,
        labels: dict[str, str] | None = None,
        trigger_kind: str = "manual",
    ) -> StartResult:
        """Admit a new run from a root event.

        Args:
            target: The root event, e.g. ``MyWorkflow.start(payload)``.
            request_key: Idempotent admission key; a repeated key returns the
                prior run with disposition ``"deduplicated"``.
            labels: Server-derived indexing labels to record on the run.
            trigger_kind: The ingress path admitting this run. It must match the
                root's declared trigger, so a webhook root cannot be started by
                application code and a manual root cannot be started by a
                provider request.

        Returns:
            The admission result.

        Raises:
            WorkflowRuntimeError: If the target is not a root, or its trigger
                does not match the admitting ingress.
        """
        defn, handler, payload = self._resolve_target(target)
        declared = getattr(handler.trigger, "kind", None)
        if declared != trigger_kind:
            expected = (
                f"trigger=rx.{trigger_kind}(...)"
                if trigger_kind == "manual"
                else f"a {trigger_kind} trigger"
            )
            msg = (
                f"Handler {handler.id!r} of {defn.workflow_id!r} declares "
                f"{declared or 'no trigger'}, so it cannot be started here; "
                f"starting through this path requires {expected}."
            )
            raise WorkflowRuntimeError(msg)
        now = self._clock()
        run_id = uuid.uuid4().hex
        run = RunRecord(
            run_id=run_id,
            workflow_id=defn.workflow_id,
            definition_digest=defn.digest,
            status=RunStatus.PENDING,
            state={field.name: field.default for field in defn.fields},
            state_version=0,
            next_ordinal=1,
            request_key=request_key,
            labels=labels,
            deadline=(now + defn.run_timeout) if defn.run_timeout is not None else None,
            created_at=now,
            updated_at=now,
        )
        root_step = StepRecord(
            run_id=run_id,
            ordinal=0,
            handler_id=handler.id,
            status=StepStatus.READY,
            args=payload,
            origin="root",
            created_at=now,
            updated_at=now,
        )
        created, authoritative_run_id = await self._store.admit(
            run,
            root_step,
            (
                (
                    HistoryEventType.RUN_ADMITTED,
                    {"handler_id": handler.id, "request_key": request_key},
                ),
                (
                    HistoryEventType.STEP_SCHEDULED,
                    {"ordinal": 0, "handler_id": handler.id},
                ),
            ),
        )
        if not created:
            return StartResult(disposition="deduplicated", run_id=authoritative_run_id)
        self._wakeup.set()
        return StartResult(disposition="started", run_id=authoritative_run_id)

    async def cancel(self, run_id: str) -> bool:
        """Request cancellation of a run.

        The in-flight attempt, if any, is cancelled cooperatively; the run is
        finalized once drained.

        Args:
            run_id: The run to cancel.

        Returns:
            True if intent was recorded on a nonterminal run.
        """
        recorded = await self._store.request_cancel(run_id, self._clock())
        if recorded:
            task = self._inflight.get(run_id)
            if task is not None:
                task.cancel()
            self._wakeup.set()
        return recorded

    async def resume(self, run_id: str) -> bool:
        """Re-open a run that is suspended for operator attention.

        Args:
            run_id: The run to resume.

        Returns:
            True if a suspended run was re-opened.
        """
        resumed = await self._store.resume_run(run_id, self._clock())
        if resumed:
            self._wakeup.set()
        return resumed

    async def list_runs(
        self,
        *,
        workflow_id: str | None = None,
        statuses: Iterable[RunStatus] = (),
        labels: Mapping[str, str] | None = None,
        created_before: float | None = None,
        limit: int = 50,
    ) -> tuple[RunRecord, ...]:
        """List runs matching a filter, newest first.

        Args:
            workflow_id: Restrict to one workflow identity.
            statuses: Restrict to these run statuses; empty means any.
            labels: Require every one of these label values.
            created_before: Pagination cursor; return runs admitted before this.
            limit: Maximum runs to return.

        Returns:
            The matching run records.
        """
        return await self._store.list_runs(
            RunQuery(
                workflow_id=workflow_id,
                statuses=tuple(statuses),
                labels=labels,
                created_before=created_before,
                limit=limit,
            )
        )

    async def get_run(self, run_id: str) -> RunSnapshot | None:
        """Load a read-only snapshot of a run.

        Args:
            run_id: The run identity.

        Returns:
            The snapshot, or None if the run is unknown.
        """
        run = await self._store.get_run(run_id)
        if run is None:
            return None
        steps = await self._store.get_steps(run_id)
        return RunSnapshot(
            run_id=run.run_id,
            workflow_id=run.workflow_id,
            status=run.status,
            state=run.state,
            state_version=run.state_version,
            result=run.result,
            error=run.error,
            steps=steps,
        )

    def _adapter(self, defn: WorkflowDefinition, field_name: str) -> TypeAdapter:
        """Get (or build) the type adapter used to coerce a loaded field value.

        Args:
            defn: The workflow definition.
            field_name: The field name.

        Returns:
            The pydantic adapter for the field's annotation.
        """
        key = (defn.workflow_id, field_name)
        adapter = self._field_adapters.get(key)
        if adapter is None:
            annotated_type = next(
                field.annotated_type
                for field in defn.fields
                if field.name == field_name
            )
            adapter = TypeAdapter(annotated_type)
            self._field_adapters[key] = adapter
        return adapter

    def _hydrate(self, defn: WorkflowDefinition, state: dict[str, Any]) -> BaseState:
        """Build a run-state instance from a committed snapshot.

        Args:
            defn: The workflow definition.
            state: The committed state snapshot.

        Returns:
            The hydrated state instance.
        """
        instance = defn.state_cls(init_substates=False, _reflex_internal_init=True)
        for field in defn.fields:
            if field.name in state:
                value = self._adapter(defn, field.name).validate_python(
                    state[field.name]
                )
                setattr(instance, field.name, value)
        return instance

    def _snapshot(
        self, defn: WorkflowDefinition, instance: BaseState
    ) -> dict[str, Any]:
        """Serialize a run-state instance into a committed snapshot.

        Args:
            defn: The workflow definition.
            instance: The state instance after the attempt.

        Returns:
            The JSON-compatible snapshot.

        Raises:
            WorkflowRuntimeError: If a field value is not serializable.
        """
        snapshot = {}
        for field in defn.fields:
            value = getattr(instance, field.name)
            try:
                snapshot[field.name] = to_run_data(value)
            except (TypeError, ValueError) as err:
                msg = (
                    f"Run state field {field.name!r} of {defn.workflow_id!r} is "
                    f"not serializable: {err}"
                )
                raise WorkflowRuntimeError(msg) from None
        return snapshot

    def _resolve_successor(
        self, defn: WorkflowDefinition, value: Any
    ) -> _SuccessorSpec:
        """Resolve one returned successor reference.

        Args:
            defn: The workflow definition of the committing run.
            value: A same-class handler reference, event spec, or ``rx.after``.

        Returns:
            The resolved successor spec.

        Raises:
            WorkflowRuntimeError: If the reference is not a durable handler on
                the same workflow class.
        """
        if isinstance(value, After):
            inner = self._resolve_successor(defn, value.target)
            inner.delay = parse_duration(value.delay)
            inner.origin = "delay"
            return inner
        successor_defn, handler, payload = self._resolve_target(value)
        if successor_defn is not defn:
            msg = (
                f"Handler {handler.id!r} belongs to {successor_defn.workflow_id!r}; "
                f"a {defn.workflow_id!r} step can only chain handlers of its own "
                "workflow class."
            )
            raise WorkflowRuntimeError(msg)
        return _SuccessorSpec(handler.id, payload)

    def _interpret_return(
        self, defn: WorkflowDefinition, value: Any
    ) -> tuple[list[_SuccessorSpec], CompleteRun | FailRun | NeedsAttention | None]:
        """Interpret a durable handler's return value.

        Args:
            defn: The workflow definition of the committing run.
            value: The handler return value.

        Returns:
            The successor specs to allocate and the control outcome, if any.

        Raises:
            WorkflowRuntimeError: If the return value is not a valid durable
                transition.
        """
        if value is None:
            return [], None
        if isinstance(value, (CompleteRun, FailRun, NeedsAttention)):
            return [], value
        if isinstance(value, (list, tuple)):
            successors = []
            for item in value:
                if isinstance(item, After):
                    msg = (
                        "rx.after(...) must be returned alone; a returned list "
                        "is an immediate sequential chain."
                    )
                    raise WorkflowRuntimeError(msg)
                successors.append(self._resolve_successor(defn, item))
            return successors, None
        return [self._resolve_successor(defn, value)], None

    async def _invoke(
        self, handler: HandlerDefinition, instance: BaseState, args: dict[str, Any]
    ) -> Any:
        """Invoke a handler attempt with its per-attempt timeout.

        Args:
            handler: The handler definition.
            instance: The hydrated run-state instance.
            args: The step payload.

        Returns:
            The handler return value.
        """
        try:
            payload = _transform_event_payload(args, handler.type_hints)
        except Exception:
            payload = dict(args)
        if handler.is_async:
            coroutine = handler.fn(instance, **payload)
        else:
            coroutine = asyncio.to_thread(handler.fn, instance, **payload)
        if handler.timeout is not None:
            return await asyncio.wait_for(coroutine, timeout=handler.timeout)
        return await coroutine

    def _build_new_steps(
        self,
        run: RunRecord,
        successors: list[_SuccessorSpec],
        now: float,
    ) -> tuple[StepRecord, ...]:
        """Allocate successor slots with preallocated ordinals.

        Args:
            run: The run record as of the claim.
            successors: The resolved successor specs.
            now: Current time in epoch seconds.

        Returns:
            The new step records in ordinal order.
        """
        return tuple(
            StepRecord(
                run_id=run.run_id,
                ordinal=run.next_ordinal + offset,
                handler_id=spec.handler_id,
                status=StepStatus.READY,
                args=spec.args,
                due_at=(now + spec.delay) if spec.delay else 0.0,
                origin=spec.origin,  # pyright: ignore[reportArgumentType]
                created_at=now,
                updated_at=now,
            )
            for offset, spec in enumerate(successors)
        )

    @staticmethod
    def _open_ordinals(steps: Iterable[StepRecord], *, exclude: int) -> tuple[int, ...]:
        """Find unresolved slots to tombstone on a final disposition.

        Args:
            steps: The run's current steps.
            exclude: The committing step's ordinal.

        Returns:
            The ordinals of unresolved slots.
        """
        return tuple(
            step.ordinal
            for step in steps
            if step.ordinal != exclude and step.status not in TERMINAL_STEP_STATUSES
        )

    def _final_failure_completion(
        self,
        defn: WorkflowDefinition,
        handler: HandlerDefinition,
        claim: Claim,
        steps: tuple[StepRecord, ...],
        *,
        step_status: StepStatus,
        run_status: RunStatus,
        hook_id: str | None,
        error: dict[str, Any],
        run_event: HistoryEventType,
        attempt_event: HistoryEventType,
        now: float,
    ) -> StepCompletion:
        """Build the commit for a step's final failure or timeout.

        Unresolved slots are tombstoned first; the declared lifecycle hook, if
        any, is then allocated as a fresh slot and the run continues through it.

        Args:
            defn: The workflow definition.
            handler: The failing handler definition.
            claim: The claim being committed.
            steps: The run's current steps.
            step_status: The step's final status.
            run_status: The run status when no hook continues the run.
            hook_id: The lifecycle hook handler id, if declared.
            error: The recorded error payload.
            run_event: History event type for the run disposition.
            attempt_event: History event type for the failing attempt.
            now: Current time in epoch seconds.

        Returns:
            The completion to commit.
        """
        tombstones = self._open_ordinals(steps, exclude=claim.step.ordinal)
        events: list[tuple[HistoryEventType, dict[str, Any]]] = [
            (attempt_event, {"ordinal": claim.step.ordinal, "error": error}),
            *(
                (HistoryEventType.STEP_TOMBSTONED, {"ordinal": ordinal})
                for ordinal in tombstones
            ),
        ]
        new_steps: tuple[StepRecord, ...] = ()
        if hook_id is not None:
            new_steps = (
                StepRecord(
                    run_id=claim.run.run_id,
                    ordinal=claim.run.next_ordinal,
                    handler_id=hook_id,
                    status=StepStatus.READY,
                    args={},
                    origin="hook",
                    created_at=now,
                    updated_at=now,
                ),
            )
            events.append((
                HistoryEventType.STEP_SCHEDULED,
                {"ordinal": claim.run.next_ordinal, "handler_id": hook_id},
            ))
            final_run_status = RunStatus.RUNNING
            run_error = None
        else:
            events.append((run_event, {"error": error}))
            final_run_status = run_status
            run_error = error
        return StepCompletion(
            step_status=step_status,
            run_status=final_run_status,
            state=None,
            consume_attempt=True,
            step_error=error,
            run_error=run_error,
            new_steps=new_steps,
            tombstones=tombstones,
            next_ordinal=claim.run.next_ordinal + len(new_steps),
            events=tuple(events),
        )

    def _failure_completion(
        self,
        defn: WorkflowDefinition,
        handler: HandlerDefinition,
        claim: Claim,
        steps: tuple[StepRecord, ...],
        error: BaseException,
        *,
        timed_out: bool,
        now: float,
    ) -> StepCompletion:
        """Build the commit for a failed or timed-out attempt.

        Args:
            defn: The workflow definition.
            handler: The handler definition.
            claim: The claim being committed.
            steps: The run's current steps.
            error: The exception raised by the attempt.
            timed_out: Whether the attempt hit its execution timeout.
            now: Current time in epoch seconds.

        Returns:
            The completion to commit.
        """
        payload = _error_payload(error)
        attempt_event = (
            HistoryEventType.ATTEMPT_TIMED_OUT
            if timed_out
            else HistoryEventType.ATTEMPT_FAILED
        )
        attempts_after = claim.step.attempts + 1
        if handler.effect == "non_idempotent_write":
            payload["reason"] = (
                "uncertain non-idempotent effect; resolve and rerun manually"
            )
            return StepCompletion(
                step_status=StepStatus.NEEDS_ATTENTION,
                run_status=RunStatus.NEEDS_ATTENTION,
                state=None,
                consume_attempt=True,
                step_error=payload,
                run_error=payload,
                events=(
                    (attempt_event, {"ordinal": claim.step.ordinal, "error": payload}),
                    (HistoryEventType.RUN_NEEDS_ATTENTION, {"error": payload}),
                ),
            )
        retryable = timed_out or handler.retry.is_retryable(error)
        if retryable and attempts_after < handler.retry.max_attempts:
            delay = handler.retry.delay_for_attempt(attempts_after)
            if handler.retry.jitter == "full":
                delay *= self._rng()
            due_at = now + delay
            return StepCompletion(
                step_status=StepStatus.RETRY_WAIT,
                run_status=RunStatus.RETRYING,
                state=None,
                consume_attempt=True,
                step_error=payload,
                due_at=due_at,
                events=(
                    (attempt_event, {"ordinal": claim.step.ordinal, "error": payload}),
                    (
                        HistoryEventType.STEP_RETRY_SCHEDULED,
                        {
                            "ordinal": claim.step.ordinal,
                            "attempt": attempts_after,
                            "due_at": due_at,
                        },
                    ),
                ),
            )
        if timed_out:
            return self._final_failure_completion(
                defn,
                handler,
                claim,
                steps,
                step_status=StepStatus.TIMED_OUT,
                run_status=RunStatus.TIMED_OUT,
                hook_id=handler.on_timeout,
                error=payload,
                run_event=HistoryEventType.RUN_TIMED_OUT,
                attempt_event=attempt_event,
                now=now,
            )
        return self._final_failure_completion(
            defn,
            handler,
            claim,
            steps,
            step_status=StepStatus.FAILED,
            run_status=RunStatus.FAILED,
            hook_id=handler.on_failure,
            error=payload,
            run_event=HistoryEventType.RUN_FAILED,
            attempt_event=attempt_event,
            now=now,
        )

    def _success_completion(
        self,
        defn: WorkflowDefinition,
        claim: Claim,
        steps: tuple[StepRecord, ...],
        state: dict[str, Any],
        successors: list[_SuccessorSpec],
        control: CompleteRun | FailRun | NeedsAttention | None,
        now: float,
    ) -> StepCompletion:
        """Build the commit for a successful attempt.

        Args:
            defn: The workflow definition.
            claim: The claim being committed.
            steps: The run's current steps.
            state: The state snapshot to commit.
            successors: Successor slots requested by the return value.
            control: Explicit control outcome, if the handler returned one.
            now: Current time in epoch seconds.

        Returns:
            The completion to commit.
        """
        events: list[tuple[HistoryEventType, dict[str, Any]]] = [
            (HistoryEventType.ATTEMPT_SUCCEEDED, {"ordinal": claim.step.ordinal})
        ]
        if isinstance(control, FailRun):
            error = {"reason": control.reason, "details": control.details}
            tombstones = self._open_ordinals(steps, exclude=claim.step.ordinal)
            events.extend(
                (HistoryEventType.STEP_TOMBSTONED, {"ordinal": ordinal})
                for ordinal in tombstones
            )
            events.append((HistoryEventType.RUN_FAILED, {"error": error}))
            return StepCompletion(
                step_status=StepStatus.SUCCEEDED,
                run_status=RunStatus.FAILED,
                state=state,
                run_error=error,
                tombstones=tombstones,
                events=tuple(events),
            )
        if isinstance(control, NeedsAttention):
            error = {"reason": control.reason, "details": control.details}
            events.append((HistoryEventType.RUN_NEEDS_ATTENTION, {"error": error}))
            # The attempt succeeded and its state is committed, but the step
            # holds the suspension so resuming knows where to pick back up.
            return StepCompletion(
                step_status=StepStatus.NEEDS_ATTENTION,
                run_status=RunStatus.NEEDS_ATTENTION,
                state=state,
                run_error=error,
                events=tuple(events),
            )
        if isinstance(control, CompleteRun):
            tombstones = self._open_ordinals(steps, exclude=claim.step.ordinal)
            events.extend(
                (HistoryEventType.STEP_TOMBSTONED, {"ordinal": ordinal})
                for ordinal in tombstones
            )
            events.append((HistoryEventType.RUN_COMPLETED, {}))
            return StepCompletion(
                step_status=StepStatus.SUCCEEDED,
                run_status=RunStatus.COMPLETED,
                state=state,
                result=self._normalize_payload({"result": control.result})["result"],
                tombstones=tombstones,
                events=tuple(events),
            )
        allocated = claim.run.next_ordinal + len(successors)
        if allocated > defn.max_steps:
            error = {
                "reason": "max_steps_exceeded",
                "max_steps": defn.max_steps,
            }
            tombstones = self._open_ordinals(steps, exclude=claim.step.ordinal)
            events.extend(
                (HistoryEventType.STEP_TOMBSTONED, {"ordinal": ordinal})
                for ordinal in tombstones
            )
            events.append((HistoryEventType.RUN_FAILED, {"error": error}))
            return StepCompletion(
                step_status=StepStatus.SUCCEEDED,
                run_status=RunStatus.FAILED,
                state=state,
                run_error=error,
                tombstones=tombstones,
                events=tuple(events),
            )
        new_steps = self._build_new_steps(claim.run, successors, now)
        events.extend(
            (
                HistoryEventType.STEP_SCHEDULED,
                {"ordinal": step.ordinal, "handler_id": step.handler_id},
            )
            for step in new_steps
        )
        open_after_commit = [
            step
            for step in (*steps, *new_steps)
            if step.ordinal != claim.step.ordinal
            and step.status not in TERMINAL_STEP_STATUSES
        ]
        if not open_after_commit:
            run_status = RunStatus.COMPLETED
            events.append((HistoryEventType.RUN_COMPLETED, {}))
        elif all(step.due_at > now for step in open_after_commit):
            run_status = RunStatus.WAITING
        else:
            run_status = RunStatus.RUNNING
        return StepCompletion(
            step_status=StepStatus.SUCCEEDED,
            run_status=run_status,
            state=state,
            new_steps=new_steps,
            next_ordinal=allocated,
            events=tuple(events),
        )

    def _acquire_lease(self, claim: Claim) -> _Lease:
        """Register an in-flight claim and start renewing its lease.

        Args:
            claim: The claim to keep alive.

        Returns:
            The lease handle.
        """
        lease = _Lease(claim)
        self._leases[claim.run.run_id] = lease
        lease.renewer = asyncio.ensure_future(self._renew_forever(lease))
        return lease

    async def _renew(self, lease: _Lease) -> None:
        """Extend one lease, abandoning the attempt when the store fences it.

        A store error is transient: the lease is left alone and the next
        renewal retries, which tolerates one lost round-trip before the lease
        could lapse.

        Args:
            lease: The lease to extend.
        """
        if lease.lost:
            return
        try:
            held = await self._store.renew_lease(
                lease.claim, self._clock(), lease_duration=self._lease_duration
            )
        except Exception as err:
            console.debug(f"Workflow lease renewal failed, retrying: {err}")
            return
        if not held:
            self._lose_lease(lease)

    async def _renew_forever(self, lease: _Lease) -> None:
        """Renew a lease on a real-time cadence until it ends or is lost.

        The cadence is real time so renewal makes progress under any injected
        clock, while the expiry written is read from the injected clock so
        virtual time alone decides when a lease has lapsed.

        Args:
            lease: The lease to renew.
        """
        while not lease.lost:
            await asyncio.sleep(self._lease_renew_interval)
            await self._renew(lease)

    def _lose_lease(self, lease: _Lease) -> None:
        """Mark a lease fenced and stop the attempt it was covering.

        Args:
            lease: The lease that was lost.
        """
        lease.lost = True
        if lease.attempt is not None:
            lease.attempt.cancel()

    async def _release_lease(self, lease: _Lease) -> None:
        """Stop renewing a lease and forget the in-flight claim.

        Args:
            lease: The lease to release.

        Raises:
            asyncio.CancelledError: If this task is cancelled while waiting for
                the renewer to stop.
        """
        self._leases.pop(lease.claim.run.run_id, None)
        renewer, lease.renewer = lease.renewer, None
        if renewer is None:
            return
        renewer.cancel()
        try:
            await renewer
        except asyncio.CancelledError:
            if not renewer.cancelled():
                raise

    async def _renew_leases(self) -> None:
        """Extend every lease this kernel holds before a recovery sweep.

        Recovery reclaims any claim whose lease has lapsed, including one this
        kernel is executing when an injected clock jumps past its expiry.
        Renewing first makes a live attempt unstealable by its own process.
        """
        for lease in list(self._leases.values()):
            await self._renew(lease)

    async def _cancel_requested(self, run_id: str) -> bool:
        """Whether a run carries cancellation intent.

        Args:
            run_id: The run to check.

        Returns:
            True when the run exists and cancellation was requested.
        """
        run = await self._store.get_run(run_id)
        return run is not None and run.cancel_requested

    async def _record_abandoned(
        self, claim: Claim, handler: HandlerDefinition, reason: str
    ) -> None:
        """Record that an attempt lost its claim and committed nothing.

        The event is appended outside the fence: the row belongs to another
        worker now, and history is append-only evidence, not state.

        Args:
            claim: The fenced claim.
            handler: The handler that was executing.
            reason: Why the claim was lost.
        """
        await self._store.append_events(
            claim.run.run_id,
            (
                (
                    HistoryEventType.ATTEMPT_ABANDONED,
                    {
                        "ordinal": claim.step.ordinal,
                        "epoch": claim.step.epoch,
                        "worker": self._worker_id,
                        "effect": handler.effect,
                        "reason": reason,
                    },
                ),
            ),
            self._clock(),
        )

    @staticmethod
    def _incompatible_reason(
        defn: WorkflowDefinition | None, claim: Claim
    ) -> dict[str, Any] | None:
        """Check that a pending step can still be dispatched after a redeploy.

        Only two changes can strand a step: the handler it names is gone, or
        its persisted payload no longer fits that handler's parameters. Adding
        state fields or retuning retries, timeouts, and hooks is safe, so those
        deploy without disturbing runs already in flight.

        Args:
            defn: The current definition of the run's workflow, if registered.
            claim: The claim about to be executed.

        Returns:
            A JSON-compatible reason when the step cannot be dispatched, else None.
        """
        if defn is None:
            return {
                "reason": "unknown_workflow",
                "workflow_id": claim.run.workflow_id,
                "detail": (
                    f"Workflow {claim.run.workflow_id!r} is no longer registered "
                    "with this app; re-register it to resume the run."
                ),
            }
        handler = defn.handlers.get(claim.step.handler_id)
        if handler is None:
            return {
                "reason": "unknown_handler",
                "handler_id": claim.step.handler_id,
                "detail": (
                    f"Handler {claim.step.handler_id!r} no longer exists on "
                    f"{claim.run.workflow_id!r}; restore it or cancel the run."
                ),
            }
        unexpected = sorted(set(claim.step.args) - set(handler.params))
        if unexpected:
            return {
                "reason": "incompatible_payload",
                "handler_id": handler.id,
                "detail": (
                    f"Step payload has arguments {unexpected} that handler "
                    f"{handler.id!r} no longer accepts; restore the parameters "
                    "or cancel the run."
                ),
            }
        return None

    async def _execute_claim(self, claim: Claim) -> None:
        """Execute one claimed attempt and commit its outcome.

        Args:
            claim: The claim to execute.
        """
        defn = self._definitions.get(claim.run.workflow_id)
        now = self._clock()
        incompatible = self._incompatible_reason(defn, claim)
        if defn is None or incompatible is not None:
            incompatible = incompatible or {"reason": "unknown_workflow"}
            await self._store.commit(
                claim,
                StepCompletion(
                    step_status=StepStatus.NEEDS_ATTENTION,
                    run_status=RunStatus.NEEDS_ATTENTION,
                    state=None,
                    step_error=incompatible,
                    run_error=incompatible,
                    events=(
                        (HistoryEventType.RUN_NEEDS_ATTENTION, dict(incompatible)),
                    ),
                ),
                now,
            )
            return
        handler = defn.handlers[claim.step.handler_id]
        steps = await self._store.get_steps(claim.run.run_id)
        await self._store.append_events(
            claim.run.run_id,
            (
                (
                    HistoryEventType.ATTEMPT_STARTED,
                    {
                        "ordinal": claim.step.ordinal,
                        "handler_id": handler.id,
                        "attempt": claim.step.attempts + 1,
                        "epoch": claim.step.epoch,
                        "effect": handler.effect,
                    },
                ),
            ),
            now,
        )
        lease = self._acquire_lease(claim)
        try:
            try:
                instance = self._hydrate(defn, claim.run.state)
                lease.attempt = asyncio.ensure_future(
                    self._invoke(handler, instance, claim.step.args)
                )
                value = await lease.attempt
            finally:
                await self._release_lease(lease)
            successors, control = self._interpret_return(defn, value)
            state = self._snapshot(defn, instance)
            completion = self._success_completion(
                defn, claim, steps, state, successors, control, self._clock()
            )
        except asyncio.CancelledError:
            if lease.lost:
                await self._record_abandoned(claim, handler, "lease_lost")
                return
            if await self._cancel_requested(claim.run.run_id):
                await self._store.release_claim(
                    claim,
                    status=StepStatus.CANCELLED,
                    events=(
                        (
                            HistoryEventType.ATTEMPT_CANCELLED,
                            {"ordinal": claim.step.ordinal},
                        ),
                    ),
                    now=self._clock(),
                )
                return
            raise
        except TimeoutError as err:
            completion = self._failure_completion(
                defn, handler, claim, steps, err, timed_out=True, now=self._clock()
            )
        except BaseException as err:
            completion = self._failure_completion(
                defn, handler, claim, steps, err, timed_out=False, now=self._clock()
            )
        try:
            await self._store.commit(claim, completion, self._clock())
        except StaleClaimError:
            await self._record_abandoned(claim, handler, "fenced_at_commit")

    async def _admit_due_schedules(self, now: float) -> int:
        """Admit a run for every schedule occurrence that has come due.

        Each occurrence is admitted under a stable request key derived from its
        exact time, so a restart, a second worker, or an overlapping sweep all
        converge on one run per occurrence rather than a stampede.

        Args:
            now: Current time in epoch seconds.

        Returns:
            The number of runs admitted.
        """
        admitted = 0
        for defn, handler, schedule in self._schedules:
            key = f"{defn.workflow_id}:{handler.id}"
            cursor = self._schedule_cursor[key]
            for occurrence in schedule.occurrences_between(
                cursor, now, limit=MAX_SCHEDULE_CATCHUP
            ):
                result = await self.start(
                    getattr(defn.state_cls, handler.name),
                    request_key=f"schedule:{key}:{int(occurrence)}",
                    trigger_kind="schedule",
                )
                admitted += result.disposition == "started"
            self._schedule_cursor[key] = now
        return admitted

    def _next_schedule_due(self, now: float) -> float | None:
        """Earliest time any registered schedule next fires.

        Args:
            now: Current time in epoch seconds.

        Returns:
            The epoch time, or None when nothing is scheduled.
        """
        upcoming = [
            occurrence
            for _, _, schedule in self._schedules
            if (occurrence := schedule.next_after(now)) is not None
        ]
        return min(upcoming) if upcoming else None

    async def _tick(self) -> bool:
        """Run one scheduling round.

        Returns:
            True if any control transition or attempt was processed.
        """
        now = self._clock()
        progressed = await self._admit_due_schedules(now) > 0
        for run in await self._store.control_pending(now):
            if run.cancel_requested:
                progressed = (
                    await self._store.finalize_run(
                        run.run_id,
                        status=RunStatus.CANCELLED,
                        error=None,
                        event=HistoryEventType.RUN_CANCELLED,
                        now=now,
                    )
                    or progressed
                )
            else:
                progressed = (
                    await self._store.finalize_run(
                        run.run_id,
                        status=RunStatus.TIMED_OUT,
                        error={"reason": "run_timeout"},
                        event=HistoryEventType.RUN_TIMED_OUT,
                        now=now,
                    )
                    or progressed
                )
        claim = await self._store.claim_next(now, lease_duration=self._lease_duration)
        if claim is not None:
            task = asyncio.ensure_future(self._execute_claim(claim))
            self._inflight[claim.run.run_id] = task
            try:
                await task
            finally:
                self._inflight.pop(claim.run.run_id, None)
            progressed = True
        return progressed

    async def recover(self) -> int:
        """Renew this kernel's live claims, then reclaim expired ones.

        A claim is reclaimable only once its lease has lapsed, so a peer that
        is mid-attempt is never disturbed and crash recovery is delayed by up
        to one lease.

        Returns:
            The number of steps recovered.
        """
        await self._renew_leases()
        now = self._clock()
        self._next_recovery_at = now + self._recovery_interval
        return await self._store.recover_orphans(now, self._max_recoveries)

    async def run_until_idle(self) -> None:
        """Process work until nothing is claimable at the current clock time.

        Each call first sweeps for claims whose lease has expired, so advancing
        the clock past a dead worker's lease reclaims its step. Scheduled
        future work (retry backoff, ``rx.after`` delays) stays pending; advance
        the clock and call again to run it.
        """
        await self.recover()
        while await self._tick():
            pass

    async def _worker_loop(self) -> None:
        """Process work continuously until the kernel is closed."""
        while True:
            try:
                if self._clock() >= self._next_recovery_at:
                    await self.recover()
                if await self._tick():
                    continue
                now = self._clock()
                due = await self._store.next_due(now)
                delay = min(self._poll_interval, max(self._next_recovery_at - now, 0.0))
                for upcoming in (due, self._next_schedule_due(now)):
                    if upcoming is not None:
                        delay = min(delay, max(upcoming - now, 0.0))
                if delay <= 0:
                    continue
                self._wakeup.clear()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._wakeup.wait(), timeout=delay)
            except Exception as err:
                console.error(f"Workflow worker error, retrying: {err}")
                await asyncio.sleep(self._poll_interval)

    async def start_worker(self) -> None:
        """Start the background worker, which recovers expired claims as it runs."""
        if self._worker is not None:
            return
        await self.recover()
        self._worker = asyncio.create_task(self._worker_loop())

    async def aclose(self) -> None:
        """Stop the background worker.

        An in-flight attempt is cancelled and its step is left claimed, so it
        is reclaimed once its lease expires rather than being recorded as a
        deliberate cancellation.
        """
        if self._worker is None:
            return
        self._worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._worker
        self._worker = None
