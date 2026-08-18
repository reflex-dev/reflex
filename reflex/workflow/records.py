"""Durable record types shared by the workflow store, kernel, and public API."""

from __future__ import annotations

import dataclasses
import enum
from typing import Any, Literal


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

    Successor slots are created ``READY`` because the in-process kernel is the
    single writer and the frontier scan already enforces mailbox order; a
    distributed kernel adapter would hold successors in a blocked state until
    their predecessor commit is visible.
    """

    READY = "READY"
    CLAIMED = "CLAIMED"
    RETRY_WAIT = "RETRY_WAIT"
    RECOVERY_WAIT = "RECOVERY_WAIT"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"


TERMINAL_STEP_STATUSES = frozenset((
    StepStatus.SUCCEEDED,
    StepStatus.FAILED,
    StepStatus.TIMED_OUT,
    StepStatus.CANCELLED,
    StepStatus.NEEDS_ATTENTION,
))

CLAIMABLE_STEP_STATUSES = frozenset((
    StepStatus.READY,
    StepStatus.RETRY_WAIT,
    StepStatus.RECOVERY_WAIT,
))


class HistoryEventType(str, enum.Enum):
    """Type of an append-only run history event."""

    RUN_ADMITTED = "run_admitted"
    STEP_SCHEDULED = "step_scheduled"
    ATTEMPT_STARTED = "attempt_started"
    ATTEMPT_SUCCEEDED = "attempt_succeeded"
    ATTEMPT_FAILED = "attempt_failed"
    ATTEMPT_TIMED_OUT = "attempt_timed_out"
    ATTEMPT_CANCELLED = "attempt_cancelled"
    STEP_RETRY_SCHEDULED = "step_retry_scheduled"
    STEP_RECOVERED = "step_recovered"
    STEP_TOMBSTONED = "step_tombstoned"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"
    RUN_TIMED_OUT = "run_timed_out"
    RUN_CANCEL_REQUESTED = "run_cancel_requested"
    RUN_CANCELLED = "run_cancelled"
    RUN_NEEDS_ATTENTION = "run_needs_attention"


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
        request_key: Idempotent admission key, if one was supplied.
        labels: Server-derived indexing labels.
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
    request_key: str | None = None
    labels: dict[str, str] | None = None
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
        error: Last recorded attempt error payload.
        origin: How the slot was allocated (root, chain, delay, or hook).
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
    error: dict[str, Any] | None = None
    origin: Literal["root", "chain", "delay", "hook"] = "chain"
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
    "buffered",
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
