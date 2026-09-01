"""Durable record types shared by the workflow store, kernel, and public API."""

from __future__ import annotations

import dataclasses
import enum
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Mapping


class RunStatus(str, enum.Enum):
    """Lifecycle status of a workflow run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    RETRYING = "RETRYING"
    WAITING = "WAITING"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"


TERMINAL_RUN_STATUSES = frozenset((
    RunStatus.CANCELLED,
    RunStatus.COMPLETED,
    RunStatus.FAILED,
    RunStatus.TIMED_OUT,
))


class StepStatus(str, enum.Enum):
    """Lifecycle status of one logical step in a run's mailbox.

    Successor slots are created ``READY`` because a slot can only be claimed
    once it is the mailbox frontier, which requires its predecessor's commit to
    be durable; a distributed kernel adapter would hold successors in a blocked
    state until that commit is visible.
    """

    READY = "READY"
    BLOCKED = "BLOCKED"
    CLAIMED = "CLAIMED"
    RETRY_WAIT = "RETRY_WAIT"
    RECOVERY_WAIT = "RECOVERY_WAIT"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"
    SKIPPED = "SKIPPED"


TERMINAL_STEP_STATUSES = frozenset((
    StepStatus.SUCCEEDED,
    StepStatus.FAILED,
    StepStatus.TIMED_OUT,
    StepStatus.CANCELLED,
    StepStatus.NEEDS_ATTENTION,
    StepStatus.SKIPPED,
))

CLAIMABLE_STEP_STATUSES = frozenset((
    StepStatus.READY,
    StepStatus.RETRY_WAIT,
    StepStatus.RECOVERY_WAIT,
))


def attempts_made(step: StepRecord) -> int:
    """How many times a slot's handler has actually been started.

    ``StepRecord.attempts`` counts what a slot has spent from its retry
    budget, and a handler that worked the first time spent nothing, so that
    field is zero for a step that plainly ran. ``recoveries`` is the same
    story for attempts a crash took away. Neither is what an operator means
    by "how many times has this run", which is what a run view shows, so this
    adds the attempt that succeeded or is in flight to both counters.

    Args:
        step: The slot to count.

    Returns:
        The number of attempts started on this slot, including one running.
    """
    started = step.attempts + step.recoveries
    if step.status in (StepStatus.SUCCEEDED, StepStatus.CLAIMED):
        return started + 1
    return started


def step_claimable_at(step: StepRecord, now: float) -> bool:
    """Whether a slot may be claimed at a point in time.

    A blocked slot is claimable only once its deadline arrives, because
    claiming it *is* the timeout branch. A blocked slot with ``due_at == 0``
    waits forever, which is why ``BLOCKED`` is deliberately not a member of
    ``CLAIMABLE_STEP_STATUSES``: that set is read by callers that do not bound
    ``due_at``, and treating a deadline-less wait as claimable would spin.

    Args:
        step: The slot to test.
        now: Current time in epoch seconds.

    Returns:
        True when the slot may be claimed right now.
    """
    if step.status in CLAIMABLE_STEP_STATUSES:
        return step.due_at <= now
    if step.status is StepStatus.BLOCKED:
        return 0.0 < step.due_at <= now
    return False


def step_wake_at(step: StepRecord) -> float | None:
    """When a slot next becomes claimable, for scheduler sleep bounds.

    Args:
        step: The slot to test.

    Returns:
        The epoch time, or None when no clock event alone can make it
        claimable, as for a wait with no deadline.
    """
    if step.status in CLAIMABLE_STEP_STATUSES:
        return step.due_at
    if step.status is StepStatus.BLOCKED and step.due_at > 0.0:
        return step.due_at
    return None


class HistoryEventType(str, enum.Enum):
    """Type of an append-only run history event."""

    RUN_ADMITTED = "run_admitted"
    STEP_SCHEDULED = "step_scheduled"
    ATTEMPT_STARTED = "attempt_started"
    ATTEMPT_SUCCEEDED = "attempt_succeeded"
    ATTEMPT_FAILED = "attempt_failed"
    ATTEMPT_TIMED_OUT = "attempt_timed_out"
    ATTEMPT_CANCELLED = "attempt_cancelled"
    ATTEMPT_ABANDONED = "attempt_abandoned"
    STEP_RETRY_SCHEDULED = "step_retry_scheduled"
    STEP_RECOVERED = "step_recovered"
    STEP_TOMBSTONED = "step_tombstoned"
    STEP_RESTORED = "step_restored"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_TIMED_OUT = "run_timed_out"
    RUN_CANCEL_REQUESTED = "run_cancel_requested"
    RUN_CANCELLED = "run_cancelled"
    RUN_NEEDS_ATTENTION = "run_needs_attention"
    RUN_RESUMED = "run_resumed"
    STEP_SKIPPED = "step_skipped"
    CHILD_STARTED = "child_started"
    CHILD_RESOLVED = "child_resolved"
    WAIT_ARMED = "wait_armed"
    WAIT_RESOLVED = "wait_resolved"
    WAIT_EXPIRED = "wait_expired"
    SUBSTEP_RECORDED = "substep_recorded"
    SIGNAL_BUFFERED = "signal_buffered"
    SIGNAL_DUPLICATE = "signal_duplicate"


@dataclasses.dataclass(frozen=True, slots=True)
class RunRecord:
    """Authoritative record of one workflow run.

    Attributes:
        run_id: Unique run identity.
        workflow_id: Stable workflow identity from ``WorkflowConfig.id``.
        definition_digest: Digest of the compiled definition the run is pinned to.
        status: Current run status.
        state: Committed run-state snapshot as JSON-compatible values.
        state_version: Monotonic version, incremented on every committed step.
        next_ordinal: Next mailbox ordinal to allocate.
        result: Run result recorded at completion.
        error: Terminal or suspension error payload.
        flow_key: Grouping key for start policies such as singleton, if any.
        parent_run_id: The run that spawned this one, if any.
        parent_ordinal: The join slot in the parent this run reports to.
        parent_close: What happens to this run when its parent reaches a
            terminal state: ``"cancel"`` or ``"abandon"``.
        request_key: Idempotent admission key, if one was supplied.
        labels: Indexing labels supplied at admission (``labels=`` on start,
            ``"labels"`` in ``POST /runs``); searchable on every surface.
        release_id: Immutable identity of the deployed artifact that admitted
            this run. Runs pin to their admitting release: a worker of a
            different release does not claim them, so one run never silently
            mixes two releases' code.
        deadline: Absolute run deadline in epoch seconds, if configured.
        cancel_requested: Whether cancellation intent has been recorded.
        created_at: Admission time in epoch seconds.
        updated_at: Last commit time in epoch seconds.
    """

    run_id: str
    workflow_id: str
    definition_digest: str
    status: RunStatus
    state: dict[str, Any]
    state_version: int
    next_ordinal: int
    result: Any = None
    error: dict[str, Any] | None = None
    flow_key: str | None = None
    parent_run_id: str | None = None
    parent_ordinal: int | None = None
    parent_close: str = "cancel"
    request_key: str | None = None
    labels: dict[str, str] | None = None
    release_id: str | None = None
    deadline: float | None = None
    cancel_requested: bool = False
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclasses.dataclass(frozen=True, slots=True)
class StepRecord:
    """One preallocated slot in a run's ordered mailbox.

    Attributes:
        run_id: The owning run.
        ordinal: Monotonic position in the mailbox; execution order.
        handler_id: Stable id of the durable handler to execute.
        status: Current step status.
        args: JSON-compatible payload passed to the handler.
        attempts: Business attempts consumed so far.
        recoveries: Infrastructure recoveries consumed so far.
        due_at: Earliest epoch time the step may be claimed.
        epoch: Fencing token, incremented on every claim.
        lease_expires_at: Epoch time this claim's lease lapses; 0 when the step
            is not claimed. A claim whose lease has lapsed is treated as
            orphaned and is reclaimed by recovery, never by a direct claim.
        wait_key: For a blocked slot, the address a delivery must carry, as
            ``"sig:<channel>"`` or ``"join:<ordinal>"``. None otherwise.
        join_expected: Arrivals required before a join slot becomes ready.
        join_arrived: Arrivals recorded so far, only ever incremented by a
            compare-and-swap so a redelivered result cannot count twice.
        error: Last recorded attempt error payload.
        origin: How the slot was allocated.
        queue: Worker queue this slot is served from. A worker claims only
            steps on queues it serves, so per-run order can flow across
            differently provisioned processes.
        created_at: Allocation time in epoch seconds.
        updated_at: Last transition time in epoch seconds.
    """

    run_id: str
    ordinal: int
    handler_id: str
    status: StepStatus
    args: dict[str, Any]
    attempts: int = 0
    recoveries: int = 0
    due_at: float = 0.0
    epoch: int = 0
    lease_expires_at: float = 0.0
    wait_key: str | None = None
    join_expected: int = 0
    join_arrived: int = 0
    error: dict[str, Any] | None = None
    origin: Literal["root", "chain", "delay", "hook", "wait", "join"] = "chain"
    queue: str = "default"
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclasses.dataclass(frozen=True, slots=True)
class HistoryEvent:
    """One append-only entry in a run's authoritative history.

    Attributes:
        run_id: The owning run.
        seq: Monotonic sequence number within the run.
        type: The event type.
        at: Event time in epoch seconds.
        data: JSON-compatible event payload.
    """

    run_id: str
    seq: int
    type: HistoryEventType
    at: float
    data: dict[str, Any]


StartDisposition = Literal[
    "started",
    "coalesced",
    "skipped",
    "rejected",
    "deduplicated",
]


@dataclasses.dataclass(frozen=True, slots=True)
class StartResult:
    """Typed result of a workflow start submission.

    Attributes:
        disposition: How admission handled the submission.
        run_id: The created or prior run, when the disposition identifies one.
        admission_id: Admission identity for buffered or coalesced work.
        retryable: Whether the caller may safely resubmit.
        retry_after: Suggested resubmission delay in seconds.
    """

    disposition: StartDisposition
    run_id: str | None = None
    admission_id: str | None = None
    retryable: bool = False
    retry_after: float | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class WorkerRecord:
    """One live worker's registration, as the fleet surface reads it.

    Attributes:
        worker_id: The worker's unique identity.
        release_id: The deployed artifact this worker runs, if declared.
        queues: The queues this worker serves; empty means every queue.
        capacity: Concurrent attempts this worker runs at most.
        started_at: When the worker registered, in epoch seconds.
        heartbeat_at: The worker's last sign of life, in epoch seconds.
    """

    worker_id: str
    release_id: str | None
    queues: tuple[str, ...]
    capacity: int
    started_at: float
    heartbeat_at: float


@dataclasses.dataclass(frozen=True, slots=True)
class AuditEntry:
    """One operator action that has no run to carry it in history.

    Run-level actions live in the run's history (§9); this is the record for
    everything else -- replaying a dead letter, purging finished runs -- so
    an operator's every mutation is attributable somewhere.

    Attributes:
        audit_id: Stable identity of the entry.
        at: When it happened, in epoch seconds.
        actor: Who asked.
        action: What was done, e.g. ``replay_parked`` or ``purge_runs``.
        target: What it was done to, e.g. a parked id or a workflow id.
        detail: Outcome and parameters, JSON-compatible.
        reason: Why, if the operator said.
    """

    audit_id: str
    at: float
    actor: str
    action: str
    target: str
    detail: dict[str, Any]
    reason: str | None


class ParkedStatus(str, enum.Enum):
    """Lifecycle of a correlated webhook delivery in the channel inbox."""

    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    DEAD = "DEAD"


@dataclasses.dataclass(frozen=True, slots=True)
class ParkedDelivery:
    """One correlated provider event, durable from the moment it was acked.

    The channel inbox is what makes webhook-to-signal delivery exactly-once:
    the row's identity is the provider's event id, so redelivery and
    crash-after-ack replays collapse into it, and a delivery that arrives
    before its run exists waits here instead of being dropped.

    Attributes:
        parked_id: Stable identity of this delivery record.
        workflow_id: The workflow whose channel the event addresses.
        channel: The channel name.
        correlation_key: The business key naming the target run.
        dedupe_key: The provider's event identity.
        payload: The canonical event payload.
        status: Where the delivery is in its lifecycle.
        reason: Why a DEAD delivery died, e.g. ``run_terminal``, ``expired``,
            or ``unclaimed``.
        run_id: The run the delivery reached, once DELIVERED.
        created_at: When the delivery was first acknowledged.
        updated_at: Last transition time.
    """

    parked_id: str
    workflow_id: str
    channel: str
    correlation_key: str
    dedupe_key: str
    payload: Any
    status: ParkedStatus
    reason: str | None
    run_id: str | None
    created_at: float
    updated_at: float


@dataclasses.dataclass(frozen=True, slots=True)
class RunQuery:
    """Filters for listing runs in an operator surface.

    Attributes:
        workflow_id: Restrict to one workflow identity.
        definition_digest: Restrict to runs admitted against one compiled
            definition. This is what answers "is anything still running the
            release I am replacing", which a deploy gate and an operator
            watching a rollout both need.
        release_id: Restrict to runs pinned to one release — with
            non-terminal ``statuses``, the "can this release's workers
            retire" question.
        statuses: Restrict to these run statuses; empty means any.
        labels: Require every one of these label values (all must match).
        created_before: Pagination cursor, as the ``(created_at, run_id)`` of
            the last row of the previous page. A fan-out stamps every child
            with the same time, so the run id breaks the tie and no run is
            skipped.
        limit: Maximum runs to return, newest first.
    """

    workflow_id: str | None = None
    definition_digest: str | None = None
    release_id: str | None = None
    statuses: tuple[RunStatus, ...] = ()
    labels: Mapping[str, str] | None = None
    created_before: tuple[float, str] | None = None
    limit: int = 50


@dataclasses.dataclass(frozen=True, slots=True)
class RunSnapshot:
    """Read-only projection of a run for operators and tests.

    Attributes:
        run_id: The run identity.
        workflow_id: The stable workflow identity.
        status: Current run status.
        state: Committed run-state values.
        state_version: Committed state version.
        result: Run result, if completed with one.
        error: Terminal or suspension error payload.
        release_id: The release that admitted the run and drains it, if any.
        steps: All mailbox slots in ordinal order.
    """

    run_id: str
    workflow_id: str
    status: RunStatus
    state: dict[str, Any]
    state_version: int
    result: Any
    error: dict[str, Any] | None
    steps: tuple[StepRecord, ...]
    release_id: str | None = None
