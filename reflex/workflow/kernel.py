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
import dataclasses
import operator
import os
import random
import time
import traceback
import uuid
from typing import TYPE_CHECKING, Any, Final

from pydantic import TypeAdapter, ValidationError
from reflex_base.event.processor.base_state_processor import _transform_event_payload
from reflex_base.utils import console
from reflex_base.utils.exceptions import WorkflowDefinitionError, WorkflowRuntimeError
from reflex_base.workflow import (
    DEFAULT_LEASE_DURATION,
    DEFAULT_MAX_RECOVERIES,
    After,
    ChannelDelivery,
    CompleteRun,
    FailRun,
    ManualTrigger,
    NeedsAttention,
    Parallel,
    ScheduleTrigger,
    WaitFor,
    _Never,
    parse_duration,
)

from reflex.event import EventHandler, EventSpec
from reflex.workflow.context import RunContext, bind_run, unbind_run
from reflex.workflow.cron import CronSchedule
from reflex.workflow.definition import unbound_params
from reflex.workflow.records import (
    TERMINAL_RUN_STATUSES,
    TERMINAL_STEP_STATUSES,
    HistoryEventType,
    RunQuery,
    RunRecord,
    RunSnapshot,
    RunStatus,
    StartResult,
    StepRecord,
    StepStatus,
    WorkerRecord,
)
from reflex.workflow.serde import to_run_data
from reflex.workflow.steps import SubstepJournal, bind_journal, unbind_journal
from reflex.workflow.store import (
    Claim,
    DeadlinePassedError,
    DeliveryDisposition,
    FlowGate,
    RunStore,
    StaleClaimError,
    StepCompletion,
    _child_admission_events,
)
from reflex.workflow.validation import canonical_payload, mistyped_args

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from reflex.state import BaseState
    from reflex.workflow.definition import HandlerDefinition, WorkflowDefinition

DEFAULT_POLL_INTERVAL = 0.25

DEFAULT_MAX_CONCURRENCY = 8

LEASE_RENEW_FRACTION = 1 / 3

RECOVERY_INTERVAL_FRACTION = 1 / 2

MAX_SCHEDULE_CATCHUP = 10
PARKED_DELIVERY_TTL = 30 * 86_400.0
"""Seconds a parked channel delivery waits for its run before dead-lettering.

Thirty days matches the longest provider retry horizons with room to spare:
a delivery still unclaimed after a month is a correlation nobody is coming
for, and an operator should see it rather than the table growing forever.
"""


class _HandlerCancelledError(Exception):
    """A handler raised CancelledError itself instead of being cancelled."""

    def __init__(self):
        """Describe the failure for the recorded error payload."""
        super().__init__(
            "handler raised CancelledError; a durable handler must not cancel "
            "itself, and must let cancellation propagate rather than raising it"
        )


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


class WorkflowObserver:
    """Receives every run transition the kernel records.

    Subclass and pass to ``rx.App(workflow_observer=...)`` to forward workflow
    activity to logs, metrics, or a tracing backend. Every call carries the
    correlation a durable system needs -- run, workflow, step, and attempt --
    so a line can be tied to the exact execution that produced it.

    Callbacks must not raise and must not block: they run on the kernel's
    event loop, and the kernel deliberately swallows their errors rather than
    letting instrumentation break execution.
    """

    def on_event(
        self,
        event_type: HistoryEventType,
        run_id: str,
        workflow_id: str,
        data: dict[str, Any],
    ) -> None:
        """Handle one recorded transition.

        Args:
            event_type: What happened.
            run_id: The run it happened to.
            workflow_id: That run's workflow identity.
            data: Event payload, such as ordinal, handler, attempt, or error.
        """

    def on_schedule_skip(self, schedule_key: str, skipped: int) -> None:
        """Handle scheduled occurrences that were dropped rather than run.

        These have no run to carry history, so without this the only trace
        of dropped work is a log line. A counter survives the process and can
        be alerted on, which is what "we silently stopped doing the nightly
        job for a week" needs.

        Args:
            schedule_key: The schedule that lost occurrences.
            skipped: How many were dropped.
        """


class CompositeObserver(WorkflowObserver):
    """Fans one transition out to several observers.

    Instrumentation is not exclusive: a deployment that exports metrics still
    wants its own logging, and neither should have to know about the other.

    Attributes:
        observers: The observers to notify, in order.
    """

    __slots__ = ("observers",)

    def __init__(self, *observers: WorkflowObserver):
        """Bind the observers to fan out to.

        Args:
            observers: The observers to notify, in order.
        """
        self.observers = observers

    def on_event(
        self,
        event_type: HistoryEventType,
        run_id: str,
        workflow_id: str,
        data: dict[str, Any],
    ) -> None:
        """Pass one transition to every observer.

        One observer raising must not cost the others their notification, and
        the kernel already treats instrumentation errors as its own to
        swallow.

        Args:
            event_type: What happened.
            run_id: The run it happened to.
            workflow_id: That run's workflow identity.
            data: The event payload.
        """
        for observer in self.observers:
            with contextlib.suppress(Exception):
                observer.on_event(event_type, run_id, workflow_id, data)

    def on_schedule_skip(self, schedule_key: str, skipped: int) -> None:
        """Pass dropped occurrences to every observer.

        Args:
            schedule_key: The schedule that lost occurrences.
            skipped: How many were dropped.
        """
        for observer in self.observers:
            with contextlib.suppress(Exception):
                observer.on_schedule_skip(schedule_key, skipped)


def _branch_index(request_key: str | None) -> int | None:
    """Recover which branch of a fan-out a child run was.

    A branch's declaration index is already durable: fan-out stamps each child
    with ``child:<parent>:<ordinal>:<index>`` as its request key, which is what
    makes a re-run of the fan-out idempotent. Reading it back is what lets a
    join report results in the order they were declared rather than the order
    they happened to finish.

    Args:
        request_key: The child run's admission key.

    Returns:
        The branch index, or None when the run was not admitted by a fan-out.
    """
    if not request_key or not request_key.startswith("child:"):
        return None
    _, _, tail = request_key.rpartition(":")
    return int(tail) if tail.isdigit() else None


class MetricsObserver(WorkflowObserver):
    """Tallies the numbers a deployment alerts on.

    The observer stream is the raw material for monitoring, but every exporter
    wants counters rather than events. This keeps the counts an operator
    actually pages on -- runs started and how they ended, attempts and how
    many were retries or recoveries -- both in total and per workflow, so a
    metrics endpoint or an OpenTelemetry exporter is a few lines over
    ``snapshot()`` rather than an event-stream parser.

    Counters only ever increase, which is what a scrape-and-diff collector
    expects. It is safe to install alongside another observer by composing
    them; a raising observer never affects a run.
    """

    _COUNTED: Final = {
        HistoryEventType.RUN_ADMITTED: "runs_started",
        HistoryEventType.RUN_COMPLETED: "runs_completed",
        HistoryEventType.RUN_FAILED: "runs_failed",
        HistoryEventType.RUN_CANCELLED: "runs_cancelled",
        HistoryEventType.RUN_TIMED_OUT: "runs_timed_out",
        HistoryEventType.RUN_NEEDS_ATTENTION: "runs_needing_attention",
        HistoryEventType.ATTEMPT_STARTED: "attempts",
        HistoryEventType.ATTEMPT_FAILED: "attempts_failed",
        HistoryEventType.ATTEMPT_TIMED_OUT: "attempts_timed_out",
        HistoryEventType.ATTEMPT_ABANDONED: "attempts_abandoned",
        HistoryEventType.STEP_RETRY_SCHEDULED: "retries_scheduled",
        HistoryEventType.STEP_RECOVERED: "steps_recovered",
        HistoryEventType.SUBSTEP_RECORDED: "substeps_recorded",
    }

    def __init__(self):
        """Start every counter at zero."""
        self.totals: dict[str, int] = {}
        self.by_workflow: dict[str, dict[str, int]] = {}

    def on_schedule_skip(self, schedule_key: str, skipped: int) -> None:
        """Count scheduled occurrences that were dropped rather than run.

        Args:
            schedule_key: The schedule that lost occurrences.
            skipped: How many were dropped.
        """
        self.totals["schedule_occurrences_skipped"] = (
            self.totals.get("schedule_occurrences_skipped", 0) + skipped
        )
        by_key = self.by_workflow.setdefault(schedule_key, {})
        by_key["schedule_occurrences_skipped"] = (
            by_key.get("schedule_occurrences_skipped", 0) + skipped
        )

    def on_event(
        self,
        event_type: HistoryEventType,
        run_id: str,
        workflow_id: str,
        data: dict[str, Any],
    ) -> None:
        """Count one transition.

        Args:
            event_type: What happened.
            run_id: The run it happened to.
            workflow_id: That run's workflow identity.
            data: Event payload.
        """
        metric = self._COUNTED.get(event_type)
        if metric is None:
            return
        self.totals[metric] = self.totals.get(metric, 0) + 1
        if workflow_id:
            counts = self.by_workflow.setdefault(workflow_id, {})
            counts[metric] = counts.get(metric, 0) + 1

    def snapshot(self) -> dict[str, Any]:
        """Read the counters as plain data.

        Returns:
            The totals, and the same counters broken down by workflow.
        """
        return {
            "totals": dict(self.totals),
            "by_workflow": {
                workflow_id: dict(counts)
                for workflow_id, counts in self.by_workflow.items()
            },
        }


class LoggingObserver(WorkflowObserver):
    """Logs every transition as a structured line."""

    def on_event(
        self,
        event_type: HistoryEventType,
        run_id: str,
        workflow_id: str,
        data: dict[str, Any],
    ) -> None:
        """Log one transition.

        Args:
            event_type: What happened.
            run_id: The run it happened to.
            workflow_id: That run's workflow identity.
            data: Event payload.
        """
        detail = " ".join(
            f"{key}={value!r}" for key, value in data.items() if key != "error"
        )
        line = f"workflow={workflow_id} run={run_id} event={event_type.value} {detail}"
        if "error" in data:
            console.warn(f"{line} error={data['error']}")
        else:
            console.debug(line)


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
        expires_at: When this lease lapses if renewal keeps failing.
        lost: Whether the store reported the claim was fenced.
    """

    __slots__ = ("attempt", "claim", "expires_at", "lost", "renewer")

    def __init__(self, claim: Claim):
        """Initialize the lease.

        Args:
            claim: The claim being kept alive.
        """
        self.claim = claim
        self.attempt: asyncio.Task | None = None
        self.renewer: asyncio.Task | None = None
        self.expires_at = claim.step.lease_expires_at
        self.lost = False


def _extract_key_field(payload: dict[str, Any], field: str) -> Any:
    """Pull a grouping value out of a start payload.

    A key may name a handler parameter directly, or a field inside a model or
    mapping parameter -- a webhook payload is one typed argument, and the
    natural key lives inside it. Compilation guarantees the name resolves
    unambiguously, so the first match here is the only one.

    Args:
        payload: The decoded start payload, by parameter name.
        field: The declared key.

    Returns:
        The value to group by, or None when the field is absent.
    """
    if field in payload:
        return payload[field]
    for value in payload.values():
        if isinstance(value, dict) and field in value:
            return value[field]
        fields = getattr(type(value), "model_fields", None)
        if fields is not None and field in fields:
            return getattr(value, field)
    return None


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
        observer: WorkflowObserver | None = None,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        queues: Iterable[str] | None = None,
        release: str | None = None,
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
            observer: Receives every recorded transition, for logging, metrics,
                or tracing.
            max_concurrency: How many attempts this kernel runs at once. Each
                belongs to a different run, so a run's own steps stay serial.
            queues: Queues this kernel's worker serves; None serves them all.
            release: The deployed artifact identity this worker runs, read
                from ``REFLEX_RELEASE_ID`` when omitted. Runs admitted here
                pin to it, and this worker never claims a run pinned to a
                different release.
                Steps land on the queue their handler declared, "default"
                otherwise, so a deployment can dedicate processes to slow or
                sensitive work.

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
        # A worker on the default clock derives time from the store instead:
        # wall clocks skew across a fleet, and a fast worker comparing its own
        # time against a peer's lease expiry reclaims a live claim -- the
        # duplicate execution leases exist to prevent. The offset is synced
        # against the store's clock at startup and on every recovery pass, so
        # skew is bounded by one round trip plus local drift per recovery
        # interval. An explicitly injected clock (tests, the dev CLI's
        # fast-forward) stays authoritative as given and is never synced.
        self._clock_anchor: tuple[float, float] | None = None
        self._sync_clock_with_store = clock is time.time
        self._clock = self._store_time if self._sync_clock_with_store else clock
        self._rng = rng
        self._poll_interval = poll_interval
        self._max_recoveries = max_recoveries
        self._max_concurrency = max(1, max_concurrency)
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
        # Filled lazily from the store on first sweep: a restart resumes the
        # previous worker's cursor, and only a schedule this deployment has
        # never seen starts from now (never backfilling its whole history).
        self._schedule_cursor: dict[str, float] = {}
        # Filled on first use rather than here: the clock is not synced with
        # the store until the first recovery pass, and a worker whose machine
        # runs slow would otherwise seed every new schedule behind store time
        # and backfill occurrences from before this deployment existed.
        self._started_at: float | None = None
        self._field_adapters: dict[tuple[str, str], TypeAdapter] = {}
        self._inflight: dict[str, asyncio.Task] = {}
        self._draining = False
        self._leases: dict[str, _Lease] = {}
        self._next_recovery_at = 0.0
        self._worker_id = uuid.uuid4().hex
        self._observer = observer
        self._queues = tuple(queues) if queues is not None else None
        self._release = (
            release if release is not None else os.environ.get("REFLEX_RELEASE_ID")
        ) or None
        self._wakeup = asyncio.Event()
        self._closing = False
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

    @staticmethod
    def _flow_key(handler: HandlerDefinition, payload: dict[str, Any]) -> str | None:
        """Compute the grouping key a start policy applies to.

        Args:
            handler: The root handler definition.
            payload: The decoded start payload.

        Returns:
            The key, or None when the handler declares no start policy.
        """
        policy = (
            handler.singleton
            or handler.rate_limit
            or handler.throttle
            or handler.debounce
        )
        if policy is None:
            return None
        field = getattr(policy, "key", None)
        if field is None:
            return handler.id
        return f"{handler.id}:{_extract_key_field(payload, field)!r}"

    async def _started_handler(self, run_id: str, handler_id: str) -> bool:
        """Whether a run's root step is the handler a delivery would start.

        Args:
            run_id: The run to check.
            handler_id: The root handler the caller wants to start.

        Returns:
            True when the run was started by that handler.
        """
        steps = await self._store.get_steps(run_id)
        return bool(steps) and steps[0].handler_id == handler_id

    async def start(
        self,
        target: Any,
        *,
        request_key: str | None = None,
        superseded_keys: tuple[str, ...] = (),
        labels: dict[str, str] | None = None,
        trigger_kind: str | None = "manual",
    ) -> StartResult:
        """Admit a new run from a root event.

        Args:
            target: The root event, e.g. ``MyWorkflow.start(payload)``.
            request_key: Idempotent admission key; a repeated key returns the
                prior run with disposition ``"deduplicated"``.
            superseded_keys: Older spellings of the same admission key, matched
                for deduplication but never recorded. This is what lets the
                key format change without every event admitted under the old
                one being admitted a second time after the upgrade.
            labels: Server-derived indexing labels to record on the run.
            trigger_kind: Which ingress is starting this run; the root must
                declare the same kind, so a webhook-only root stays
                unreachable from the browser. None skips the gate -- the test
                harness's privilege, where the test author is the trigger.

        Returns:
            The admission result.

        Raises:
            WorkflowRuntimeError: If the target is not a root, or its trigger
                does not match the admitting ingress.
        """
        defn, handler, payload = self._resolve_target(target)
        unbound = sorted(unbound_params(handler, set(payload)))
        problems = mistyped_args(handler, payload)
        if unbound or problems:
            # Refused before anything is written: admitting this run would
            # only postpone the same message to its first dispatch, minus the
            # stack frame that shows the caller which call site is wrong.
            faults = [
                *(f"missing required argument {name!r}" for name in unbound),
                *problems,
            ]
            msg = (
                f"Cannot start {handler.id!r} of {defn.workflow_id!r}: "
                f"{'; '.join(faults)}."
            )
            raise WorkflowDefinitionError(msg)
        declared = getattr(handler.trigger, "kind", None)
        # A handler without a trigger is a mid-flow step, not a root; no
        # ingress -- and no test privilege -- makes it startable.
        if declared is None or (trigger_kind is not None and declared != trigger_kind):
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
        # Dedupe before any start policy: a redelivered event must return the
        # run it already created, not be judged as a new start and cancel,
        # throttle, or debounce that very run.
        existing = (
            None
            if request_key is None
            else await self._store.find_by_request_key(defn.workflow_id, request_key)
        )
        if existing is None:
            for candidate in superseded_keys:
                # A superseded key is matched but never written, so a key
                # format can change without every event admitted under the old
                # one arriving twice. The old spelling was less specific than
                # the new one, though, so a match on it only means the same
                # event if it started the same root -- otherwise the very
                # collision the new format fixed comes back through the
                # compatibility path.
                found = await self._store.find_by_request_key(
                    defn.workflow_id, candidate
                )
                if found is not None and await self._started_handler(found, handler.id):
                    existing = found
                    break
        if existing is not None:
            return StartResult(disposition="deduplicated", run_id=existing)
        flow_key = self._flow_key(handler, payload)
        if flow_key is None:
            return await self._admit(defn, handler, payload, request_key, labels, None)
        # A start policy is a read followed by a write, and only the store can
        # make the pair atomic: an in-process lock serializes one process, and
        # a fleet is not one process. The whole decision executes inside a
        # single store transaction under a durable lock on the flow key.
        now = self._clock()
        singleton = handler.singleton
        gate = FlowGate(
            singleton_skip=singleton is not None and singleton.mode == "skip",
            singleton_cancel=singleton is not None and singleton.mode == "cancel",
            rate_limit=(
                (handler.rate_limit.limit, parse_duration(handler.rate_limit.period))
                if handler.rate_limit is not None
                else None
            ),
            throttle=(
                (handler.throttle.limit, parse_duration(handler.throttle.period))
                if handler.throttle is not None
                else None
            ),
            debounce=(
                parse_duration(handler.debounce.period)
                if handler.debounce is not None
                else None
            ),
        )
        run, root_step, admission = self._admission_records(
            defn, handler, payload, request_key, labels, flow_key, now
        )
        outcome = await self._store.admit_flow(run, root_step, admission, gate, now)
        for cancelled_id in outcome.cancelled:
            # Durable intent was written in the admitting transaction; what is
            # left is this process's share -- stop a local in-flight attempt
            # and tell the observer.
            await self._notify_run(
                cancelled_id, ((HistoryEventType.RUN_CANCEL_REQUESTED, {}),)
            )
            task = self._inflight.get(cancelled_id)
            if task is not None:
                task.cancel()
        if outcome.cancelled:
            await self._finalize_control(self._clock())
        if outcome.disposition == "started":
            self._notify(run, admission)
            self._wakeup.set()
            return StartResult(disposition="started", run_id=outcome.run_id)
        if outcome.disposition == "rejected":
            return StartResult(
                disposition="rejected",
                retryable=True,
                retry_after=outcome.retry_after,
            )
        return StartResult(disposition=outcome.disposition, run_id=outcome.run_id)

    def _admission_records(
        self,
        defn: WorkflowDefinition,
        handler: HandlerDefinition,
        payload: dict[str, Any],
        request_key: str | None,
        labels: dict[str, str] | None,
        flow_key: str | None,
        now: float,
        due_at: float | None = None,
    ) -> tuple[
        RunRecord,
        StepRecord,
        tuple[tuple[HistoryEventType, dict[str, Any]], ...],
    ]:
        """Build the records one admission writes.

        Args:
            defn: The workflow definition.
            handler: The root handler.
            payload: The decoded start payload.
            request_key: Idempotent admission key.
            labels: Server-derived indexing labels.
            flow_key: Start-policy grouping key, if the root declares one.
            now: Current time in epoch seconds.
            due_at: Earliest start time, when a policy delayed it.

        Returns:
            The run record, its root slot, and the admission history events.
        """
        run_id = uuid.uuid4().hex
        run = RunRecord(
            run_id=run_id,
            workflow_id=defn.workflow_id,
            definition_digest=defn.digest,
            status=RunStatus.PENDING,
            state={field.name: field.default for field in defn.fields},
            state_version=0,
            next_ordinal=1,
            flow_key=flow_key,
            request_key=request_key,
            labels=labels,
            release_id=self._release,
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
            due_at=now if due_at is None else due_at,
            origin="root",
            queue=handler.queue or "default",
            created_at=now,
            updated_at=now,
        )
        admission = (
            (
                HistoryEventType.RUN_ADMITTED,
                {"handler_id": handler.id, "request_key": request_key},
            ),
            (
                HistoryEventType.STEP_SCHEDULED,
                {"ordinal": 0, "handler_id": handler.id},
            ),
        )
        return run, root_step, admission

    async def _admit(
        self,
        defn: WorkflowDefinition,
        handler: HandlerDefinition,
        payload: dict[str, Any],
        request_key: str | None,
        labels: dict[str, str] | None,
        flow_key: str | None,
        due_at: float | None = None,
    ) -> StartResult:
        """Create the run and its root slot for a policy-free root.

        Roots that declare a start policy go through ``admit_flow`` instead,
        where the whole decision is one store transaction.

        Args:
            defn: The workflow definition.
            handler: The root handler.
            payload: The decoded start payload.
            request_key: Idempotent admission key.
            labels: Server-derived indexing labels.
            flow_key: Start-policy grouping key, if the root declares one.
            due_at: Earliest start time, when a policy delayed it.

        Returns:
            The admission result.
        """
        now = self._clock()
        run, root_step, admission = self._admission_records(
            defn, handler, payload, request_key, labels, flow_key, now, due_at
        )
        created, authoritative_run_id = await self._store.admit(
            run, root_step, admission
        )
        if not created:
            return StartResult(disposition="deduplicated", run_id=authoritative_run_id)
        self._notify(run, admission)
        self._wakeup.set()
        return StartResult(disposition="started", run_id=authoritative_run_id)

    @staticmethod
    def _attribution(actor: str | None, reason: str | None) -> dict[str, str] | None:
        """Build the who-and-why payload an operator event carries.

        Args:
            actor: Who asked, if known.
            reason: Why, if given.

        Returns:
            The attribution mapping, or None when neither is known.
        """
        payload = {
            key: value for key, value in (("actor", actor), ("reason", reason)) if value
        }
        return payload or None

    async def cancel(
        self,
        run_id: str,
        *,
        actor: str | None = None,
        reason: str | None = None,
    ) -> bool:
        """Request cancellation of a run.

        The in-flight attempt, if any, is cancelled cooperatively; the run is
        finalized once drained.

        Args:
            run_id: The run to cancel.
            actor: Who asked, recorded in the run's history.
            reason: Why, recorded alongside.

        Returns:
            True if intent was recorded on a nonterminal run.
        """
        attribution = self._attribution(actor, reason)
        recorded = await self._store.request_cancel(run_id, self._clock(), attribution)
        if recorded:
            await self._notify_run(
                run_id,
                ((HistoryEventType.RUN_CANCEL_REQUESTED, dict(attribution or {})),),
            )
            task = self._inflight.get(run_id)
            if task is not None:
                task.cancel()
            self._wakeup.set()
        return recorded

    def _workflow_id_of(self, workflow: Any) -> str:
        """Resolve a workflow argument to its stable identity.

        Args:
            workflow: A registered workflow class, or a workflow id string.

        Returns:
            The workflow id.

        Raises:
            WorkflowRuntimeError: If the workflow is not registered here.
        """
        if isinstance(workflow, str):
            if workflow in self._definitions:
                return workflow
        else:
            defn = self._definitions_by_cls.get(workflow)
            if defn is not None:
                return defn.workflow_id
        known = ", ".join(sorted(self._definitions)) or "<none>"
        msg = (
            f"Workflow {workflow!r} is not registered with this runtime; "
            f"registered: {known}."
        )
        raise WorkflowRuntimeError(msg)

    async def find_by_key(self, workflow: Any, request_key: str) -> str | None:
        """Find the run a business key admitted, if any.

        The request key is already a durable unique index -- it is what makes
        webhook redelivery idempotent -- so it doubles as the business
        address of a run: ``order_123`` finds the order's run without anyone
        having threaded the engine's run id through their own tables.

        Args:
            workflow: The registered workflow class or its id.
            request_key: The admission key the run was started under.

        Returns:
            The run id, or None when the key admitted nothing.
        """
        return await self._store.find_by_request_key(
            self._workflow_id_of(workflow), request_key
        )

    async def ingest_channel(
        self,
        workflow_id: str,
        channel_name: str,
        correlation_key: str,
        dedupe_key: str,
        payload: Any,
    ) -> DeliveryDisposition:
        """Durably accept a correlated webhook delivery for a channel.

        Args:
            workflow_id: The workflow whose channel the event addresses.
            channel_name: The channel name.
            correlation_key: The business key naming the target run.
            dedupe_key: The provider's event identity.
            payload: The canonical event payload.

        Returns:
            The routing outcome.

        Raises:
            WorkflowDefinitionError: If the workflow is registered here and
                does not declare the channel.
        """
        defn = self._definitions.get(workflow_id)
        if defn is not None and channel_name not in defn.channels:
            declared = sorted(defn.channels) or ["<none>"]
            msg = (
                f"Workflow {workflow_id!r} declares no channel "
                f"{channel_name!r}; declared channels: {', '.join(declared)}."
            )
            raise WorkflowDefinitionError(msg)
        disposition = await self._store.ingest_channel_delivery(
            workflow_id,
            channel_name,
            correlation_key,
            dedupe_key,
            to_run_data({"value": payload})["value"],
            self._clock(),
        )
        if disposition == "resolved":
            self._wakeup.set()
        return disposition

    async def signal_by_key(
        self,
        workflow: Any,
        request_key: str,
        delivery: ChannelDelivery,
        *,
        key: str | None = None,
    ) -> DeliveryDisposition:
        """Deliver a signal to the run a business key admitted.

        Args:
            workflow: The registered workflow class or its id.
            request_key: The admission key the run was started under.
            delivery: The addressed payload, e.g. ``Order.shipped(payload)``.
            key: Sender idempotency key; a repeated key is a no-op.

        Returns:
            What the store did with the delivery, or ``"unknown_key"`` when
            the key admitted nothing.
        """
        run_id = await self.find_by_key(workflow, request_key)
        if run_id is None:
            return "unknown_key"
        return await self.signal(run_id, delivery, key=key)

    async def signal(
        self,
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

        Raises:
            WorkflowDefinitionError: If the run's workflow is registered here
                and does not declare the channel, or the payload does not
                satisfy the channel's declared model.
        """
        payload = delivery.payload
        run = await self._store.get_run(run_id)
        defn = self._definitions.get(run.workflow_id) if run is not None else None
        if defn is not None:
            channel = defn.channels.get(delivery.channel)
            if channel is None:
                # A typo'd channel would buffer forever: the store cannot
                # know the name is wrong, so the sender must hear it here,
                # from the process that knows what the workflow declares.
                declared = sorted(defn.channels) or ["<none>"]
                msg = (
                    f"Workflow {defn.workflow_id!r} declares no channel "
                    f"{delivery.channel!r}; declared channels: "
                    f"{', '.join(declared)}."
                )
                raise WorkflowDefinitionError(msg)
            if channel.model is not None:
                # Every route into a channel validates the same way --
                # including deliveries built without Signal.__call__, such
                # as approval-token redemptions -- and what goes onward is
                # the canonical form the model promises, not the raw input.
                try:
                    payload = canonical_payload(channel.model, payload)
                except ValidationError as error:
                    msg = (
                        f"Channel {delivery.channel!r} of "
                        f"{defn.workflow_id!r} expects "
                        f"{channel.model.__name__}: {error.error_count()} "
                        "validation error(s)."
                    )
                    raise WorkflowDefinitionError(msg) from error
        disposition = await self._store.deliver(
            run_id,
            f"sig:{delivery.channel}",
            key or uuid.uuid4().hex,
            to_run_data({"value": payload})["value"],
            self._clock(),
        )
        if disposition == "resolved":
            await self._notify_run(
                run_id,
                (
                    (
                        HistoryEventType.WAIT_RESOLVED,
                        {"wait_key": f"sig:{delivery.channel}"},
                    ),
                ),
            )
            self._wakeup.set()
        elif disposition == "buffered":
            await self._notify_run(
                run_id,
                (
                    (
                        HistoryEventType.SIGNAL_BUFFERED,
                        {"wait_key": f"sig:{delivery.channel}"},
                    ),
                ),
            )
        elif disposition == "duplicate":
            # Correctly a no-op, but a no-op nobody can see is
            # indistinguishable from a delivery that never arrived.
            await self._notify_run(
                run_id,
                (
                    (
                        HistoryEventType.SIGNAL_DUPLICATE,
                        {"wait_key": f"sig:{delivery.channel}"},
                    ),
                ),
            )
        return disposition

    async def resume(
        self,
        run_id: str,
        *,
        actor: str | None = None,
        reason: str | None = None,
    ) -> bool:
        """Re-open a run that is suspended for operator attention.

        Args:
            run_id: The run to resume.
            actor: Who asked, recorded in the run's history.
            reason: Why, recorded alongside.

        Returns:
            True if a suspended run was re-opened.
        """
        resumed = await self._store.resume_run(
            run_id, self._clock(), self._attribution(actor, reason)
        )
        if resumed:
            await self._notify_run(
                run_id,
                (
                    (
                        HistoryEventType.RUN_RESUMED,
                        dict(self._attribution(actor, reason) or {}),
                    ),
                ),
            )
            self._wakeup.set()
        return resumed

    async def retry(
        self,
        run_id: str,
        *,
        actor: str | None = None,
        reason: str | None = None,
    ) -> bool:
        """Re-open a failed run at the step that failed.

        Args:
            run_id: The run to retry.
            actor: Who asked, recorded in the run's history.
            reason: Why, recorded alongside.

        Returns:
            True if a failed run was re-opened.
        """
        retried = await self._store.retry_run(
            run_id, self._clock(), self._attribution(actor, reason)
        )
        if retried:
            await self._notify_run(
                run_id, ((HistoryEventType.RUN_RESUMED, {"origin": "retry"}),)
            )
            self._wakeup.set()
        return retried

    async def skip(
        self,
        run_id: str,
        *,
        actor: str | None = None,
        reason: str | None = None,
    ) -> bool:
        """Skip the step blocking a stopped run and let it continue.

        Args:
            run_id: The run to unstick.
            actor: Who asked, recorded in the run's history.
            reason: Why, recorded alongside.

        Returns:
            True if a blocking step was skipped.
        """
        skipped = await self._store.skip_step(
            run_id, self._clock(), self._attribution(actor, reason)
        )
        if skipped:
            await self._notify_run(
                run_id, ((HistoryEventType.STEP_SKIPPED, {"origin": "operator"}),)
            )
            self._wakeup.set()
        return skipped

    async def force_finalize(
        self,
        run_id: str,
        *,
        status: RunStatus,
        result: Any = None,
        error: dict[str, Any] | None = None,
        actor: str | None = None,
        reason: str | None = None,
    ) -> bool:
        """End a run by operator decision, tombstoning what it had open.

        The escape hatch for a run no code path will finish: a wait nobody
        will answer, a branch whose provider is gone. Refused while any step
        is claimed, so it never races a working attempt -- cancel first if a
        worker still holds it.

        Args:
            run_id: The run to finalize.
            actor: Who asked, recorded in the run's history.
            reason: Why, recorded alongside.
            status: The terminal status to record.
            result: Result to record when completing.
            error: Error payload to record when failing.

        Returns:
            True if the run was finalized.
        """
        now = self._clock()
        run = await self._store.get_run(run_id)
        if run is None:
            return False
        # An operator's result is run data like any other. Passing it through
        # unchecked let Memory keep a live Decimal that no other store could
        # hold, while SQLite raised a bare "not JSON serializable" from inside
        # json.dumps -- the same input, three behaviours, none of them saying
        # what to do about it.
        result = to_run_data({"value": result})["value"] if result is not None else None
        # The error payload is stored beside the result and read back the same
        # way, so it faces the same rules: an operator reason carrying a
        # Decimal or bytes would fail at the store, or worse, only on some
        # stores.
        error = to_run_data(error) if error is not None else None
        event = (
            HistoryEventType.RUN_COMPLETED
            if status is RunStatus.COMPLETED
            else HistoryEventType.RUN_FAILED
        )
        finalized = await self._store.finalize_run(
            run_id,
            status=status,
            error=error,
            event=event,
            now=now,
            result=result,
            parent_arrival=self._arrival_for(run, status, result, error),
            attribution=self._attribution(actor, reason),
        )
        if finalized:
            self._notify(run, ((event, {"origin": "operator"}),))
            await self._report_outcome(run, status, result, error)
        return finalized

    async def list_runs(
        self,
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
            release_id=run.release_id,
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
    ) -> tuple[
        list[_SuccessorSpec],
        CompleteRun | FailRun | NeedsAttention | WaitFor | Parallel | None,
    ]:
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
        if isinstance(value, (CompleteRun, FailRun, NeedsAttention, WaitFor, Parallel)):
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

    async def _in_declaration_order(self, results: list) -> list:
        """Sort a join's arrivals into the order their branches were declared.

        An arrival carries its branch index. One recorded before that field
        existed does not, and a join can span the upgrade that introduced it,
        so the index is recovered from the branch's admission key -- which
        every release has written, because it is what makes re-running a
        fan-out idempotent. Anything still unidentifiable keeps its arrival
        position rather than being reordered on a guess.

        Args:
            results: The arrivals recorded on the join slot.

        Returns:
            The arrivals in declaration order where that is knowable.
        """
        ordered: list[tuple[int, Any]] = []
        for position, entry in enumerate(results):
            branch = entry.get("branch") if isinstance(entry, dict) else None
            if not isinstance(branch, int) and isinstance(entry, dict):
                run_id = entry.get("run_id")
                child = (
                    await self._store.get_run(run_id)
                    if isinstance(run_id, str)
                    else None
                )
                if child is not None:
                    branch = _branch_index(child.request_key)
            ordered.append((branch if isinstance(branch, int) else position, entry))
        return [entry for _, entry in sorted(ordered, key=operator.itemgetter(0))]

    async def _invoke(
        self,
        handler: HandlerDefinition,
        instance: BaseState,
        args: dict[str, Any],
        context: RunContext,
        journal: SubstepJournal,
    ) -> Any:
        """Invoke a handler attempt with its per-attempt timeout.

        Args:
            handler: The handler definition.
            instance: The hydrated run-state instance.
            args: The step payload.
            context: Identity of this attempt, readable inside the handler.
            journal: Recorded substeps of this step, for ``rx.step``.

        Returns:
            The handler return value.
        """
        args = {key: value for key, value in args.items() if key != "__wait__"}
        delivered = args.pop("__payload__", None)
        results = args.pop("__results__", None)
        if isinstance(results, list):
            # A join accumulates arrivals as they land, which is finishing
            # order; rx.parallel promises declaration order, and a caller
            # unpacking `a, b = results` has no other way to tell which is
            # which.
            results = await self._in_declaration_order(results)
        if delivered is None and results is not None:
            delivered = results
        if delivered is not None and handler.params:
            args[handler.params[0]] = delivered
        try:
            payload = _transform_event_payload(args, handler.type_hints)
        except Exception:
            payload = dict(args)
        token = bind_run(context)
        journal_token = bind_journal(journal)
        try:
            if handler.is_async:
                coroutine = handler.fn(instance, **payload)
            else:
                # to_thread copies the current context, so a sync handler sees
                # the same attempt identity as an async one.
                coroutine = asyncio.to_thread(handler.fn, instance, **payload)
            if handler.timeout is not None:
                return await asyncio.wait_for(coroutine, timeout=handler.timeout)
            return await coroutine
        finally:
            unbind_journal(journal_token)
            unbind_run(token)

    def _queue_of(self, defn: WorkflowDefinition, handler_id: str) -> str:
        """Resolve the worker queue a handler's steps are served from.

        Args:
            defn: The workflow definition.
            handler_id: The handler naming the step.

        Returns:
            The queue name.
        """
        return defn.handlers[handler_id].queue or "default"

    async def _build_journal(self, claim: Claim) -> SubstepJournal:
        """Load the substeps recorded for a step and bind them to this attempt.

        Args:
            claim: The fenced claim being executed.

        Returns:
            The journal ``rx.step`` reads and writes.
        """
        recorded = await self._store.get_substeps(claim.run.run_id, claim.step.ordinal)

        def notify(key: str) -> None:
            """Report one newly recorded substep to the observer.

            Args:
                key: The substep's memoization key.
            """
            self._notify(
                claim.run,
                (
                    (
                        HistoryEventType.SUBSTEP_RECORDED,
                        {"ordinal": claim.step.ordinal, "key": key},
                    ),
                ),
            )

        return SubstepJournal(
            store=self._store,
            run_id=claim.run.run_id,
            ordinal=claim.step.ordinal,
            epoch=claim.step.epoch,
            recorded=recorded,
            clock=self._clock,
            notify=notify,
            loop=asyncio.get_running_loop(),
            sync_timeout=max(self._lease_duration * 2.0, 30.0),
        )

    def _build_new_steps(
        self,
        defn: WorkflowDefinition,
        run: RunRecord,
        successors: list[_SuccessorSpec],
        now: float,
    ) -> tuple[StepRecord, ...]:
        """Allocate successor slots with preallocated ordinals.

        Args:
            defn: The workflow definition, for per-handler queues.
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
                queue=self._queue_of(defn, spec.handler_id),
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

    def _control_error(self, reason: str, details: Any) -> dict[str, Any]:
        """Build a durable error payload from a control return.

        ``details`` comes from user code, so it is normalized here rather than
        at commit: an unserializable value must not break the transaction that
        is recording the failure.

        Args:
            reason: The stable failure reason.
            details: Whatever the handler attached.

        Returns:
            A JSON-compatible error payload.
        """
        if details is None:
            return {"reason": reason, "details": None}
        try:
            return {"reason": reason, "details": to_run_data(details)}
        except (TypeError, ValueError):
            return {"reason": reason, "details": {"unserializable": repr(details)}}

    def _success_completion(
        self,
        defn: WorkflowDefinition,
        claim: Claim,
        steps: tuple[StepRecord, ...],
        state: dict[str, Any],
        successors: list[_SuccessorSpec],
        control: CompleteRun | FailRun | NeedsAttention | WaitFor | Parallel | None,
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
            error = self._control_error(control.reason, control.details)
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
            error = self._control_error(control.reason, control.details)
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
        if isinstance(control, Parallel):
            children = self._child_records(
                claim,
                control.branches,
                claim.run.next_ordinal,
                now,
                control.parent_close,
            )
            then_id = self._resolve_successor(defn, control.then).handler_id
            join = StepRecord(
                run_id=claim.run.run_id,
                ordinal=claim.run.next_ordinal,
                handler_id=then_id,
                status=StepStatus.BLOCKED,
                args={"__results__": []},
                wait_key=f"join:{claim.run.next_ordinal}",
                join_expected=1 if control.mode == "first" else len(control.branches),
                origin="join",
                queue=self._queue_of(defn, then_id),
                created_at=now,
                updated_at=now,
            )
            events.append((
                HistoryEventType.CHILD_STARTED,
                {
                    "ordinal": join.ordinal,
                    "branches": len(control.branches),
                    "mode": control.mode,
                },
            ))
            return StepCompletion(
                step_status=StepStatus.SUCCEEDED,
                run_status=RunStatus.WAITING,
                state=state,
                new_steps=(join,),
                next_ordinal=claim.run.next_ordinal + 1,
                events=tuple(events),
                children=children,
            )
        if isinstance(control, WaitFor):
            resume = self._resolve_successor(defn, control.then)
            timeout_id = (
                self._resolve_successor(defn, control.on_timeout).handler_id
                if control.on_timeout is not None
                else None
            )
            deadline = (
                0.0
                if isinstance(control.timeout, _Never)
                else now + parse_duration(control.timeout)
            )
            wait_key = f"sig:{control.channel}"
            slot = StepRecord(
                run_id=claim.run.run_id,
                ordinal=claim.run.next_ordinal,
                handler_id=resume.handler_id,
                status=StepStatus.BLOCKED,
                args={
                    **resume.args,
                    "__wait__": {
                        "channel": control.channel,
                        "on_timeout": timeout_id,
                        # Which step asked the question. An approval link is
                        # minted while that step runs, so this is what lets a
                        # link be checked against the question it belongs to
                        # rather than against whatever is waiting now.
                        "armed_by": claim.step.ordinal,
                    },
                },
                due_at=deadline,
                wait_key=wait_key,
                origin="wait",
                queue=self._queue_of(defn, resume.handler_id),
                created_at=now,
                updated_at=now,
            )
            events.append((
                HistoryEventType.WAIT_ARMED,
                {
                    "ordinal": slot.ordinal,
                    "wait_key": wait_key,
                    "deadline": deadline or None,
                },
            ))
            return StepCompletion(
                step_status=StepStatus.SUCCEEDED,
                run_status=RunStatus.WAITING,
                state=state,
                new_steps=(slot,),
                next_ordinal=claim.run.next_ordinal + 1,
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
        new_steps = self._build_new_steps(defn, claim.run, successors, now)
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

    async def _record(
        self,
        run: RunRecord,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
        now: float,
    ) -> None:
        """Append history events and tell the observer about them.

        Args:
            run: The run the transitions belong to.
            events: The (type, data) pairs to record.
            now: Current time in epoch seconds.
        """
        await self._store.append_events(run.run_id, events, now)
        self._notify(run, events)

    async def _notify_run(
        self,
        run_id: str,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
    ) -> None:
        """Tell the observer about transitions a store operation recorded.

        Some transitions are written by the store itself, inside the same
        transaction as the state change they describe. The kernel knows which
        ones those are from the operation's result, and reports them here so
        the observer sees one stream rather than the subset the kernel happens
        to construct itself.

        The run is loaded only to correlate the events with their workflow, so
        a deployment without an observer pays nothing for this.

        Args:
            run_id: The run the transitions belong to.
            events: The (type, data) pairs the store recorded.
        """
        if self._observer is None:
            return
        run = await self._store.get_run(run_id)
        if run is not None:
            self._notify(run, events)

    def _notify(
        self,
        run: RunRecord,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
    ) -> None:
        """Hand recorded transitions to the observer, if one is installed.

        Instrumentation must never break execution, so an observer that raises
        is reported and ignored.

        Args:
            run: The run the transitions belong to.
            events: The (type, data) pairs just recorded.
        """
        if self._observer is None:
            return
        try:
            for event_type, data in events:
                self._observer.on_event(event_type, run.run_id, run.workflow_id, data)
        except Exception as err:
            console.warn(f"Workflow observer raised, ignoring: {err}")

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
        now = self._clock()
        try:
            held = await self._store.renew_lease(
                lease.claim, now, lease_duration=self._lease_duration
            )
        except Exception as err:
            # The lease keeps ticking down while renewal fails. Once too little
            # of it remains to survive another failed round-trip, stop the
            # attempt rather than keep running work this kernel can no longer
            # prove it owns -- recovery is about to hand the step to someone else.
            if lease.expires_at - now <= self._lease_renew_interval:
                console.warn(
                    "Workflow lease renewal keeps failing and the lease is about "
                    f"to lapse; abandoning the attempt: {err}"
                )
                self._lose_lease(lease)
            else:
                console.debug(f"Workflow lease renewal failed, retrying: {err}")
            return
        if not held:
            self._lose_lease(lease)
            return
        lease.expires_at = now + self._lease_duration

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
            # The error may be the renewer's echo, or a cancellation aimed at
            # THIS task landing while it waited here. Swallowing the latter
            # consumes the caller's one cancellation -- a task shut down
            # during this await would keep running, which is how a process
            # gets a task that outlives teardown forever. Our own pending
            # cancellation always re-raises.
            current = asyncio.current_task()
            if (current is not None and current.cancelling()) or (
                not renewer.cancelled()
            ):
                raise

    async def _renew_leases(self) -> None:
        """Extend every lease this kernel holds before a recovery sweep.

        Recovery reclaims any claim whose lease has lapsed, including one this
        kernel is executing when an injected clock jumps past its expiry.
        Renewing first makes a live attempt unstealable by its own process.
        """
        for lease in list(self._leases.values()):
            await self._renew(lease)
        if self._worker is not None:
            # The same cadence that proves claims alive proves the worker
            # alive; a heartbeat needing its own timer would drift from the
            # one signal operators actually watch.
            await self._store.heartbeat_worker(self._worker_id, self._clock())

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
        await self._record(
            claim.run,
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
        supplied = {key for key in claim.step.args if not key.startswith("__")}
        unexpected = sorted(supplied - set(handler.params))
        if handler.params and (
            # A wait's continuation, a join, and a child arrival are all
            # handed their first argument at dispatch rather than carrying it
            # in the recorded payload, so it is supplied even though the
            # recorded args do not name it.
            "__payload__" in claim.step.args
            or "__results__" in claim.step.args
            or "__wait__" in claim.step.args
        ):
            supplied.add(handler.params[0])
        missing = sorted(unbound_params(handler, supplied))
        if missing:
            # A parameter added with no default is the mirror image of a
            # deleted one, and just as much a redeploy problem: the recorded
            # payload cannot fill it. Dispatching anyway fails the run with a
            # TypeError from deep inside the handler, which tells the operator
            # nothing about what to ship to fix it.
            return {
                "reason": "incompatible_payload",
                "handler_id": handler.id,
                "detail": (
                    f"Handler {handler.id!r} now requires {missing}, which the "
                    "recorded payload does not carry; give them defaults, or "
                    "cancel the run."
                ),
            }
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
        wrong = mistyped_args(handler, claim.step.args)
        if wrong:
            # A recorded value that no longer fits the parameter's type is a
            # redeploy problem exactly like a renamed parameter: the payload
            # was valid when it was recorded and the code changed underneath
            # it. Dispatching anyway raises from inside the handler and
            # burns retry attempts on a state no retry can change.
            return {
                "reason": "incompatible_payload",
                "handler_id": handler.id,
                "detail": (
                    f"Recorded payload no longer fits handler {handler.id!r}: "
                    f"{'; '.join(wrong)}. Restore the parameter types, or "
                    "cancel the run."
                ),
            }
        return None

    @staticmethod
    def _expired_wait_handler(
        defn: WorkflowDefinition, claim: Claim
    ) -> HandlerDefinition | None:
        """Pick the timeout branch when a wait is claimed at its deadline.

        A wait resolved by a delivery arrives carrying a payload; a wait
        claimed without one reached its deadline, so the timeout branch runs
        instead of the resume branch.

        Args:
            defn: The workflow definition.
            claim: The claim being executed.

        Returns:
            The timeout handler, or None when the wait was resolved normally.
        """
        wait = claim.step.args.get("__wait__")
        if not isinstance(wait, dict) or "__payload__" in claim.step.args:
            return None
        timeout_id = wait.get("on_timeout")
        return defn.handlers.get(timeout_id) if timeout_id else None

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
        wait_events: tuple[tuple[HistoryEventType, dict[str, Any]], ...] = ()
        if claim.step.status is StepStatus.CLAIMED and claim.step.wait_key is not None:
            expired = self._expired_wait_handler(defn, claim)
            if expired is not None:
                handler = expired
                # A resolved wait records WAIT_RESOLVED at delivery; without
                # this, an expired one recorded nothing, and the only trace of
                # the deadline was which handler happened to run next.
                wait_events = (
                    (
                        HistoryEventType.WAIT_EXPIRED,
                        {
                            "wait_key": claim.step.wait_key,
                            "ordinal": claim.step.ordinal,
                            "on_timeout": expired.id,
                        },
                    ),
                )
        steps = await self._store.get_steps(claim.run.run_id)
        await self._record(
            claim.run,
            (
                *wait_events,
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
                    self._invoke(
                        handler,
                        instance,
                        claim.step.args,
                        RunContext(
                            run_id=claim.run.run_id,
                            workflow_id=claim.run.workflow_id,
                            ordinal=claim.step.ordinal,
                            handler_id=handler.id,
                            attempt=claim.step.attempts + 1,
                            epoch=claim.step.epoch,
                        ),
                        await self._build_journal(claim),
                    )
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
            # asyncio marks a task cancelled whether we cancelled it or the
            # handler let CancelledError escape, so the task's own flag cannot
            # tell them apart. Discriminate on this kernel's control signals
            # instead; anything else came from user code.
            if lease.lost:
                await self._record_abandoned(claim, handler, "lease_lost")
                return
            if await self._cancel_requested(claim.run.run_id):
                cancelled = (
                    (
                        HistoryEventType.ATTEMPT_CANCELLED,
                        {"ordinal": claim.step.ordinal},
                    ),
                )
                await self._store.release_claim(
                    claim,
                    status=StepStatus.CANCELLED,
                    events=cancelled,
                    now=self._clock(),
                )
                self._notify(claim.run, cancelled)
                return
            current = asyncio.current_task()
            if self._closing or (current is not None and current.cancelling()):
                # Someone cancelled *us* -- worker shutdown or a supervising
                # task -- so this is crash-equivalent: leave the step claimed
                # for lease recovery rather than recording an outcome.
                raise
            completion = self._failure_completion(
                defn,
                handler,
                claim,
                steps,
                _HandlerCancelledError(),
                timed_out=False,
                now=self._clock(),
            )
            await self._commit_outcome(claim, handler, completion)
            return
        except TimeoutError as err:
            completion = self._failure_completion(
                defn, handler, claim, steps, err, timed_out=True, now=self._clock()
            )
        except BaseException as err:
            completion = self._failure_completion(
                defn, handler, claim, steps, err, timed_out=False, now=self._clock()
            )
        await self._commit_outcome(claim, handler, completion)

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
        paused = (
            await self._store.paused_schedules() if self._schedules else frozenset()
        )
        for defn, handler, schedule in self._schedules:
            key = f"{defn.workflow_id}:{handler.id}"
            cursor = self._schedule_cursor.get(key)
            if cursor is None:
                # A restart must resume where the last worker stopped, not
                # skip the downtime: an in-memory cursor seeded at startup
                # treats every missed occurrence as already fired.
                stored = await self._store.read_schedule_cursor(key)
                if self._started_at is None:
                    # Recovery sets this at startup, right after the clock is
                    # synced, which is the value that matters. Reaching here
                    # means a kernel that swept without ever recovering; "now"
                    # is still the right seed, just an unsynced one.
                    self._started_at = self._clock()
                cursor = stored if stored is not None else self._started_at
                self._schedule_cursor[key] = cursor
            if key in paused:
                # A paused schedule skips its occurrences and keeps its cursor
                # moving, so resuming never backfills the pause: an operator
                # who paused a nightly job for a week wants one run when they
                # resume, not seven. Skipped occurrences are not "lost work"
                # -- they were asked for -- so they feed no alert counter,
                # but they are said out loud.
                skipped = schedule.count_between(cursor, now)
                if skipped:
                    console.warn(
                        f"Schedule {key} is paused; skipping {skipped} "
                        f"occurrence(s) between {cursor:.0f} and {now:.0f}."
                    )
                self._schedule_cursor[key] = now
                await self._store.write_schedule_cursor(key, now)
                continue
            occurrences = schedule.occurrences_between(
                cursor, now, limit=MAX_SCHEDULE_CATCHUP + 1
            )
            if len(occurrences) > MAX_SCHEDULE_CATCHUP:
                # The cursor is about to jump over these. Silently losing
                # scheduled work reads as "covered" when it was not; the
                # operator gets the count and the window, and can start the
                # missed occurrences by hand if they matter.
                # Counted rather than sampled: a second bounded query would
                # undercount a long outage exactly when the number matters
                # most, and the count is what an alert fires on.
                dropped = schedule.count_between(cursor, now) - MAX_SCHEDULE_CATCHUP
                occurrences = occurrences[:MAX_SCHEDULE_CATCHUP]
                # A log line is the only trace these otherwise leave, and they
                # have no run to carry history. A counter survives the process
                # and can be alerted on, which is what noticing "the nightly
                # job silently stopped for a week" actually needs.
                if self._observer is not None:
                    with contextlib.suppress(Exception):
                        self._observer.on_schedule_skip(key, max(dropped, 1))
                console.warn(
                    f"Schedule {key} missed more than {MAX_SCHEDULE_CATCHUP} "
                    f"occurrences between {cursor:.0f} and {now:.0f}; catching "
                    f"up the first {MAX_SCHEDULE_CATCHUP} and skipping the "
                    "rest. Start any that matter with rx.workflows.start()."
                )
            for occurrence in occurrences:
                result = await self.start(
                    getattr(defn.state_cls, handler.name),
                    request_key=f"schedule:{key}:{int(occurrence)}",
                    trigger_kind="schedule",
                )
                admitted += result.disposition == "started"
            self._schedule_cursor[key] = now
            await self._store.write_schedule_cursor(key, now)
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

    def _child_records(
        self,
        claim: Claim,
        branches: tuple[Any, ...],
        join_ordinal: int,
        now: float,
        parent_close: str,
    ) -> tuple[tuple[RunRecord, StepRecord], ...]:
        """Build the child runs a fan-out will create.

        They are built here, not admitted separately afterwards, so the store
        can insert them in the same transaction as the join slot: a crash can
        never leave a join waiting on children that were never created.

        Args:
            claim: The parent's claim.
            branches: The root events to run concurrently.
            join_ordinal: The join slot the children report to.
            now: Current time in epoch seconds.
            parent_close: What happens to a branch still running when the
                parent reaches a terminal state.

        Returns:
            Each child run paired with its root slot.
        """
        records = []
        for index, branch in enumerate(branches):
            defn, handler, payload = self._resolve_target(branch)
            if not isinstance(handler.trigger, ManualTrigger):
                msg = (
                    f"Cannot fan out to {handler.id!r} of {defn.workflow_id!r}: "
                    f"it declares {getattr(handler.trigger, 'kind', 'no trigger')}, "
                    "and a branch must be a manual root just like a direct start."
                )
                raise WorkflowRuntimeError(msg)
            if (
                handler.singleton is not None
                or handler.rate_limit is not None
                or handler.throttle is not None
                or handler.debounce is not None
            ):
                # Fan-out writes its children in the parent's committing
                # transaction rather than through policy admission, so a
                # policy on a branch root would be silently bypassed -- five
                # branches under a throttle of two all start at once, and
                # nothing says so. Refusing is honest until branches go
                # through the same admission primitive as a direct start.
                msg = (
                    f"Cannot fan out to {handler.id!r} of {defn.workflow_id!r}: "
                    "it declares a start policy (singleton, rate_limit, "
                    "throttle, or debounce), and fan-out admits branches "
                    "directly, bypassing policies. Remove the policy from "
                    "this root, or start it as its own run with "
                    "rx.workflows.start()."
                )
                raise WorkflowDefinitionError(msg)
            child_id = uuid.uuid4().hex
            records.append((
                RunRecord(
                    run_id=child_id,
                    workflow_id=defn.workflow_id,
                    definition_digest=defn.digest,
                    status=RunStatus.PENDING,
                    state={field.name: field.default for field in defn.fields},
                    state_version=0,
                    release_id=self._release,
                    next_ordinal=1,
                    parent_run_id=claim.run.run_id,
                    parent_ordinal=join_ordinal,
                    parent_close=parent_close,
                    request_key=f"child:{claim.run.run_id}:{join_ordinal}:{index}",
                    deadline=(
                        now + defn.run_timeout if defn.run_timeout is not None else None
                    ),
                    created_at=now,
                    updated_at=now,
                ),
                StepRecord(
                    run_id=child_id,
                    ordinal=0,
                    handler_id=handler.id,
                    status=StepStatus.READY,
                    args=payload,
                    origin="root",
                    queue=handler.queue or "default",
                    created_at=now,
                    updated_at=now,
                ),
            ))
        return tuple(records)

    async def _commit_outcome(
        self, claim: Claim, handler: HandlerDefinition, completion: StepCompletion
    ) -> None:
        """Commit an attempt's outcome and follow up on what it scheduled.

        Args:
            claim: The claim being committed.
            handler: The handler that ran.
            completion: The outcome to apply.
        """
        completion = self._with_parent_arrival(claim.run, completion)
        try:
            await self._store.commit(claim, completion, self._clock())
        except StaleClaimError:
            await self._record_abandoned(claim, handler, "fenced_at_commit")
            return
        except DeadlinePassedError:
            # The run passed its deadline while this attempt ran. The only
            # permitted outcome now is the sweep's TIMED_OUT, so the attempt
            # is abandoned -- its recorded substeps stand, crash-equivalent --
            # and its slot is released so the run drains immediately instead
            # of waiting out a lease.
            abandoned = (
                (
                    HistoryEventType.ATTEMPT_ABANDONED,
                    {
                        "ordinal": claim.step.ordinal,
                        "epoch": claim.step.epoch,
                        "worker": self._worker_id,
                        "effect": handler.effect,
                        "reason": "deadline_passed",
                    },
                ),
            )
            with contextlib.suppress(StaleClaimError):
                await self._store.release_claim(
                    claim,
                    status=StepStatus.CANCELLED,
                    events=abandoned,
                    now=self._clock(),
                )
            self._notify(claim.run, abandoned)
            self._wakeup.set()
            return
        self._notify(claim.run, completion.events)
        for child_run, child_step in completion.children:
            # The store recorded each child's admission inside the commit;
            # the observer hears the same events, so runs_started counts a
            # four-run graph as four.
            self._notify(child_run, _child_admission_events(child_run, child_step))
        if completion.children:
            self._wakeup.set()
        await self._report_to_parent(claim.run, completion)

    @staticmethod
    def _arrival_for(
        run: RunRecord,
        status: RunStatus,
        result: Any = None,
        error: dict[str, Any] | None = None,
    ) -> tuple[str, int, dict[str, Any], str] | None:
        """Build the arrival a terminating run owes its parent, if any.

        Args:
            run: The run that is ending.
            status: Its terminal status.
            result: Its result, if any.
            error: Its error, if any.

        Returns:
            The arrival tuple, or None when the run has no parent.
        """
        if run.parent_run_id is None or run.parent_ordinal is None:
            return None
        return (
            run.parent_run_id,
            run.parent_ordinal,
            {
                "run_id": run.run_id,
                "status": status.value,
                "result": result,
                "error": error,
                "branch": _branch_index(run.request_key),
            },
            run.run_id,
        )

    @staticmethod
    def _with_parent_arrival(
        run: RunRecord, completion: StepCompletion
    ) -> StepCompletion:
        """Attach a child's parent arrival so it commits with the transition.

        A child that finishes and a parent that hears about it must become
        true together. Delivering afterwards leaves a window where a crash
        strands the join forever, waiting on a child that is already done.

        Args:
            run: The run being committed, which may have no parent.
            completion: The outcome about to be applied.

        Returns:
            The completion, carrying the arrival when one is owed.
        """
        if (
            run.parent_run_id is None
            or run.parent_ordinal is None
            or completion.run_status not in TERMINAL_RUN_STATUSES
        ):
            return completion
        return dataclasses.replace(
            completion,
            parent_arrival=(
                run.parent_run_id,
                run.parent_ordinal,
                {
                    "run_id": run.run_id,
                    "status": completion.run_status.value,
                    "result": completion.result,
                    "error": completion.run_error,
                    "branch": _branch_index(run.request_key),
                },
                run.run_id,
            ),
        )

    async def _report_to_parent(
        self, run: RunRecord, completion: StepCompletion
    ) -> None:
        """Follow up on an arrival that committed with the child's transition.

        The arrival itself is already durable (see _with_parent_arrival); what
        remains is advisory: waking the parent's worker and, for a decided
        race, cancelling the branches that lost.

        Args:
            run: The child run, which may have no parent.
            completion: The committed outcome that finished it.
        """
        if (
            completion.run_status not in TERMINAL_RUN_STATUSES
            or run.parent_run_id is None
            or run.parent_ordinal is None
        ):
            return
        await self._notify_run(
            run.parent_run_id,
            (
                (
                    HistoryEventType.CHILD_RESOLVED,
                    {"ordinal": run.parent_ordinal, "child": run.run_id},
                ),
            ),
        )
        parent_steps = await self._store.get_steps(run.parent_run_id)
        join = next(
            (step for step in parent_steps if step.ordinal == run.parent_ordinal),
            None,
        )
        if join is not None and join.status is not StepStatus.BLOCKED:
            await self._cancel_losing_branches(run)
        self._wakeup.set()

    async def _report_outcome(
        self,
        run: RunRecord,
        status: RunStatus,
        result: Any,
        error: dict[str, Any] | None,
    ) -> None:
        """Tell a parent's join that this child has finished, however it finished.

        Cancellation and run deadlines terminate a child without a commit, so
        this is called from both paths: a join must never wait forever on a
        child that has already stopped.

        Args:
            run: The child run, which may have no parent.
            status: Its terminal status.
            result: Its result, if any.
            error: Its error, if any.
        """
        if run.parent_run_id is None or run.parent_ordinal is None:
            return
        disposition = await self._store.record_arrival(
            run.parent_run_id,
            run.parent_ordinal,
            {
                "run_id": run.run_id,
                "status": status.value,
                "result": result,
                "error": error,
                "branch": _branch_index(run.request_key),
            },
            run.run_id,
            self._clock(),
        )
        if disposition in ("resolved", "counted"):
            await self._notify_run(
                run.parent_run_id,
                (
                    (
                        HistoryEventType.CHILD_RESOLVED,
                        {"ordinal": run.parent_ordinal, "child": run.run_id},
                    ),
                ),
            )
        if disposition == "resolved":
            await self._cancel_losing_branches(run)
        self._wakeup.set()

    async def _cancel_losing_branches(self, winner: RunRecord) -> None:
        """Cancel the siblings a decided race left running.

        A join satisfied before every branch reported means the rest can no
        longer affect the outcome, so leaving them running would burn work and
        keep making external calls nobody is waiting for.

        Args:
            winner: The child whose arrival satisfied the join.
        """
        if winner.parent_run_id is None or winner.parent_ordinal is None:
            return
        join = next(
            (
                step
                for step in await self._store.get_steps(winner.parent_run_id)
                if step.ordinal == winner.parent_ordinal
            ),
            None,
        )
        if join is None or join.join_expected != 1:
            # Only a race has losers. An all-mode join wants every branch, and
            # a join that stopped being blocked for some other reason -- a
            # cancelled or force-finalized parent tombstones it -- has not
            # decided anything. Cancelling siblings on either would be this
            # engine reaching into runs it does not own, which §5 says
            # delegation does not do.
            return
        if join.status is StepStatus.CANCELLED:
            return
        siblings = await self._store.list_children(
            winner.parent_run_id, winner.parent_ordinal
        )
        for sibling in siblings:
            if (
                sibling.run_id != winner.run_id
                and sibling.status not in TERMINAL_RUN_STATUSES
            ):
                await self.cancel(sibling.run_id)

    async def _finalize_control(self, now: float) -> int:
        """Finalize every drained run awaiting a control transition.

        Args:
            now: Current time in epoch seconds.

        Returns:
            How many runs were finalized.
        """
        finalized = 0
        for run in await self._store.control_pending(now):
            cancelled = run.cancel_requested
            status = RunStatus.CANCELLED if cancelled else RunStatus.TIMED_OUT
            error = None if cancelled else {"reason": "run_timeout"}
            event = (
                HistoryEventType.RUN_CANCELLED
                if cancelled
                else HistoryEventType.RUN_TIMED_OUT
            )
            if await self._store.finalize_run(
                run.run_id,
                status=status,
                error=error,
                event=event,
                now=now,
                parent_arrival=self._arrival_for(run, status, None, error),
            ):
                self._notify(run, ((event, {} if error is None else dict(error)),))
                await self._report_outcome(run, status, None, error)
                finalized += 1
        return finalized

    def _spawn(self, claim: Claim) -> asyncio.Task:
        """Start executing a claim, tracking it until it finishes.

        Args:
            claim: The claim to execute.

        Returns:
            The task running the attempt.
        """
        task = asyncio.ensure_future(self._execute_claim(claim))
        self._inflight[claim.run.run_id] = task
        return task

    def _prune(self) -> int:
        """Drop finished attempts from the in-flight set.

        Pruning is synchronous rather than done-callback driven: a callback
        runs on a later loop iteration, so the scheduler would keep seeing
        completed work as in flight and spin.

        Returns:
            How many attempts had finished.
        """
        finished = [run_id for run_id, task in self._inflight.items() if task.done()]
        for run_id in finished:
            del self._inflight[run_id]
        return len(finished)

    async def _fill_slots(self, now: float) -> list[asyncio.Task]:
        """Claim work up to this kernel's concurrency limit.

        Each run has one frontier, so two concurrent claims are always
        different runs: parallelism across runs never breaks the serial
        mailbox each run relies on.

        Args:
            now: Current time in epoch seconds.

        Returns:
            The attempts this call started.
        """
        started: list[asyncio.Task] = []
        while len(self._inflight) < self._max_concurrency:
            claim = await self._store.claim_next(
                now,
                lease_duration=self._lease_duration,
                queues=self._queues,
                release=self._release,
            )
            if claim is None:
                break
            started.append(self._spawn(claim))
        return started

    async def _tick(self, own: set[asyncio.Task] | None = None) -> bool:
        """Run one scheduling round.

        Args:
            own: When given, the attempts this round starts are added, so the
                caller can later drain exactly what it started and nothing a
                concurrent pump owns.

        Returns:
            True if any control transition or attempt was processed.
        """
        now = self._clock()
        progressed = self._prune() > 0
        progressed = await self._admit_due_schedules(now) > 0 or progressed
        progressed = await self._finalize_control(now) > 0 or progressed
        started = await self._fill_slots(now)
        if own is not None:
            own.update(started)
        progressed = bool(started) or progressed
        # Wait only on what this round started: another caller pumping the same
        # kernel must not block on an attempt it does not own.
        if started:
            try:
                await asyncio.wait(started, return_when=asyncio.FIRST_COMPLETED)
            except asyncio.CancelledError:
                # asyncio.wait does not cancel what it waits on, so cancelling
                # the scheduler must stop the attempts it started or they run
                # on unsupervised -- and only those: with several pumps on one
                # kernel, another pump's attempts are its own to supervise,
                # and the closer's aclose() sweeps whatever remains. A drain
                # is the exception: there the closer is waiting on them
                # itself and cancels the leftovers.
                if not self._draining:
                    for task in started:
                        task.cancel()
                    await asyncio.gather(*started, return_exceptions=True)
                    self._prune()
                raise
            progressed = self._prune() > 0 or progressed
        return progressed

    async def _cancel_inflight(self) -> None:
        """Stop every attempt this kernel is running and wait for them."""
        tasks = list(self._inflight.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._prune()

    def _store_time(self) -> float:
        """The store's clock, carried forward by monotonic elapsed time.

        The wall clock is read once per sync and never between them. NTP
        steps, a resumed snapshot, or an operator correcting a drifted host
        all move ``time.time`` without warning, and a worker that added a
        fixed offset to it moved with it -- renewing its lease to a moment
        the store considers past, so its claim lapsed mid-attempt and a peer
        reclaimed the step. ``time.monotonic`` cannot jump, so the only error
        left is real drift since the last sync, which the next recovery pass
        corrects.

        Returns:
            Epoch seconds by the store's clock, to within one sync error.
        """
        if self._clock_anchor is None:
            return time.time()
        store_at_sync, monotonic_at_sync = self._clock_anchor
        return store_at_sync + (time.monotonic() - monotonic_at_sync)

    async def _sync_store_clock(self) -> None:
        """Re-measure the offset between this process and the store's clock.

        The store's answer is taken against the midpoint of the request, so
        the measured offset is off by at most half the round trip.
        """
        if not self._sync_clock_with_store:
            return
        before = time.monotonic()
        store_now = await self._store.epoch_time()
        after = time.monotonic()
        if store_now is None:
            # The process clock is the authority for this store; stop asking.
            self._sync_clock_with_store = False
            self._clock_anchor = None
            return
        # The store answered somewhere inside the round trip, so credit it to
        # the midpoint: the anchor is then off by at most half of one.
        self._clock_anchor = (store_now, (before + after) / 2)

    async def recover(self) -> int:
        """Renew this kernel's live claims, then reclaim expired ones.

        A claim is reclaimable only once its lease has lapsed, so a peer that
        is mid-attempt is never disturbed and crash recovery is delayed by up
        to one lease.

        Returns:
            The number of steps recovered.
        """
        await self._sync_store_clock()
        if self._started_at is None:
            # Now, and not a moment before: this is the seed for a schedule
            # this deployment has never seen, and taking it from an unsynced
            # clock on a slow machine backfills occurrences from before the
            # deployment existed. Recovery runs before the first sweep, so
            # the seed is still "when this worker started".
            self._started_at = self._clock()
        await self._renew_leases()
        now = self._clock()
        swept = await self._store.sweep_parked(now, PARKED_DELIVERY_TTL)
        if swept:
            console.warn(
                f"{swept} parked channel deliver{'y' if swept == 1 else 'ies'} "
                "went unclaimed past the TTL and became dead letters; "
                "list them with the store's list_parked and replay any that "
                "matter."
            )
        self._next_recovery_at = now + self._recovery_interval
        recovered, failed = await self._store.recover_orphans(now, self._max_recoveries)
        for run_id in failed:
            run = await self._store.get_run(run_id)
            if run is not None:
                await self._report_outcome(
                    run,
                    RunStatus.FAILED,
                    None,
                    {"reason": "recovery_budget_exhausted"},
                )
        return recovered

    async def run_until_idle(self) -> None:
        """Process work until nothing is claimable at the current clock time.

        Each call first sweeps for claims whose lease has expired, so advancing
        the clock past a dead worker's lease reclaims its step. Scheduled
        future work (retry backoff, ``rx.after`` delays) stays pending; advance
        the clock and call again to run it.
        """
        await self.recover()
        own: set[asyncio.Task] = set()
        while True:
            if await self._tick(own):
                continue
            # A round can start several attempts and return after the first
            # completion, so "nothing newly claimable" is not "nothing
            # running": returning here hands a test a half-processed graph
            # and cancels the survivors when the harness exits. Idle means no
            # claimable work AND none of the attempts THIS pump started still
            # live -- an attempt some other caller owns (a hanging handler a
            # test controls, a concurrent pump's work) is not ours to wait on.
            own = {task for task in own if not task.done()}
            if not own:
                return
            try:
                await asyncio.wait(own, return_when=asyncio.FIRST_COMPLETED)
            except asyncio.CancelledError:
                # A cancelled pump must stop the attempts it started or they
                # run on unsupervised -- but only its own: another pump's
                # attempts are that pump's to supervise, and cancelling them
                # from here turns one caller's timeout into another's lost
                # work.
                if not self._draining:
                    for task in own:
                        task.cancel()
                    await asyncio.gather(*own, return_exceptions=True)
                    self._prune()
                raise
            self._prune()

    async def _worker_loop(self) -> None:
        """Process work continuously until the kernel is closed."""
        while True:
            try:
                if self._clock() >= self._next_recovery_at:
                    await self.recover()
                if await self._tick():
                    continue
                if len(self._inflight) >= self._max_concurrency:
                    # Every slot is busy, so the only thing that can change is
                    # an attempt finishing; due times cannot matter until one
                    # does. A round normally blocks on the attempts it started,
                    # so this is a guard on the invariant rather than a path
                    # the loop is expected to take.
                    await asyncio.wait(
                        list(self._inflight.values()),
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    continue
                now = self._clock()
                due = await self._store.next_due(now, queues=self._queues)
                delay = min(self._poll_interval, max(self._next_recovery_at - now, 0.0))
                for upcoming in (due, self._next_schedule_due(now)):
                    if upcoming is not None:
                        delay = min(delay, max(upcoming - now, 0.0))
                if delay <= 0:
                    continue
                self._wakeup.clear()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._wakeup.wait(), timeout=delay)
            except asyncio.CancelledError:
                # Cancellation is never a retryable error. Catching it here --
                # which `except BaseException` did -- made the worker
                # unkillable by anything except aclose(): a supervisor, a task
                # group, or an event loop shutting down would cancel it, be
                # told nothing, and wait forever for a task that had already
                # gone back to polling.
                raise
            except Exception as err:
                console.error(f"Workflow worker error, retrying: {err!r}")
                await asyncio.sleep(self._poll_interval)

    async def start_worker(self) -> None:
        """Start the background worker, which recovers expired claims as it runs."""
        if self._worker is not None and not self._worker.done():
            return
        self._closing = False
        await self.recover()
        now = self._clock()
        # Registered after the first recovery so the clock is store-synced;
        # the fleet surface is how a deploy gate can see who runs which
        # release, at what capacity, and how recently they proved alive.
        await self._store.register_worker(
            WorkerRecord(
                worker_id=self._worker_id,
                release_id=self._release,
                queues=self._queues or (),
                capacity=self._max_concurrency,
                started_at=now,
                heartbeat_at=now,
            )
        )
        self._worker = asyncio.create_task(self._worker_loop())

    async def aclose(self, drain: float = 0.0) -> None:
        """Stop the background worker.

        Claiming stops immediately. With a drain budget, attempts already
        running are given that long to commit their own outcome, which is what
        makes a rolling deploy cheap: a step that finishes during the drain is
        durable before the process leaves, instead of sitting claimed until
        its lease lapses.

        An attempt still running when the budget runs out is cancelled and its
        step is left claimed, so it is reclaimed once the lease expires rather
        than being recorded as a deliberate cancellation. The claim is not
        released early on purpose: cancelling an attempt does not stop work it
        handed to a thread, and the lease is what keeps a peer from running
        the step alongside it.

        Args:
            drain: Seconds to let in-flight attempts finish before cancelling.
        """
        if self._worker is None:
            return
        self._closing = True
        self._draining = drain > 0.0
        self._worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._worker
        self._worker = None
        # A clean shutdown removes the registration; a crash leaves it with a
        # stale heartbeat, which is exactly what a fleet page should show.
        with contextlib.suppress(Exception):
            await self._store.deregister_worker(self._worker_id)
        if self._inflight and self._draining:
            await asyncio.wait(set(self._inflight.values()), timeout=drain)
        self._draining = False
        # The kernel owns its attempts, so closing it stops them rather than
        # leaving them running against a store nobody is reading any more.
        await self._cancel_inflight()
