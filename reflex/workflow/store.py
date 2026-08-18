"""Durable run stores for the workflow kernel.

A store is the single authority for run state: admission with idempotent
request keys, the ordered per-run mailbox, claim fencing and leasing, and the
atomic step commit that persists a state patch together with its successor
slots. The kernel decides what should happen; the store makes it durable
atomically.

``MemoryRunStore`` backs tests and the harness. ``SqliteRunStore`` provides
crash-safe persistence on a single machine using the standard library. Run
exactly one worker process per database file: its calls are synchronous and
cross-process write contention blocks the caller's event loop, which is
hostile to lease renewal.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import sqlite3
import threading
from typing import TYPE_CHECKING, Any, Final, Protocol

from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import DEFAULT_LEASE_DURATION

from reflex.workflow.records import (
    CLAIMABLE_STEP_STATUSES,
    TERMINAL_RUN_STATUSES,
    TERMINAL_STEP_STATUSES,
    HistoryEvent,
    HistoryEventType,
    RunRecord,
    RunStatus,
    StepRecord,
    StepStatus,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


class StaleClaimError(WorkflowRuntimeError):
    """Raised when a commit no longer owns its claim and must be discarded."""


@dataclasses.dataclass(frozen=True, slots=True)
class Claim:
    """A fenced claim on the frontier step of one run.

    Attributes:
        run: The run record as of the claim.
        step: The step record after the claim transition.
    """

    run: RunRecord
    step: StepRecord


@dataclasses.dataclass(frozen=True, slots=True)
class StepCompletion:
    """Atomic outcome of one executed attempt, applied by ``commit``.

    Attributes:
        step_status: Final step status for this commit.
        run_status: Run status after this commit.
        state: Committed state snapshot, or None to discard the attempt's patch.
        consume_attempt: Whether this outcome consumes a business attempt.
        step_error: Error payload recorded on the step.
        run_error: Error payload recorded on the run.
        result: Run result, for completing commits.
        due_at: Earliest next claim time, for ``RETRY_WAIT``.
        new_steps: Successor slots to append, with preallocated ordinals.
        tombstones: Ordinals of unresolved slots to cancel.
        next_ordinal: Updated mailbox allocation counter, if slots were added.
        events: History events to append, in order, as (type, data) pairs.
    """

    step_status: StepStatus
    run_status: RunStatus
    state: dict[str, Any] | None
    consume_attempt: bool = False
    step_error: dict[str, Any] | None = None
    run_error: dict[str, Any] | None = None
    result: Any = None
    due_at: float | None = None
    new_steps: tuple[StepRecord, ...] = ()
    tombstones: tuple[int, ...] = ()
    next_ordinal: int | None = None
    events: tuple[tuple[HistoryEventType, dict[str, Any]], ...] = ()


class RunStore(Protocol):
    """Protocol implemented by workflow run stores."""

    async def admit(
        self,
        run: RunRecord,
        root_step: StepRecord,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
    ) -> tuple[bool, str]:
        """Atomically admit a run, deduplicating on the request key.

        Args:
            run: The run record to create.
            root_step: The preallocated root mailbox slot.
            events: History events to append on creation.

        Returns:
            ``(True, run_id)`` when the run was created, or
            ``(False, existing_run_id)`` when the request key already admitted one.
        """
        ...

    async def claim_next(
        self, now: float, *, lease_duration: float = DEFAULT_LEASE_DURATION
    ) -> Claim | None:
        """Claim the due frontier step of some runnable run.

        The claim carries a lease expiring at ``now + lease_duration``. The
        executing kernel must renew it through ``renew_lease``; a claim whose
        lease lapses is reclaimed by ``recover_orphans``.

        Args:
            now: Current time in epoch seconds.
            lease_duration: Seconds of renewal silence tolerated before the
                claim is treated as orphaned.

        Returns:
            A fenced claim, or None when nothing is claimable right now.
        """
        ...

    async def renew_lease(
        self,
        claim: Claim,
        now: float,
        *,
        lease_duration: float = DEFAULT_LEASE_DURATION,
    ) -> bool:
        """Extend a live claim's lease without transitioning the step.

        Renewal is a liveness signal only: it must not change the step's
        status, fencing epoch, or any committed state, and it never consumes a
        budget.

        Args:
            claim: The claim being renewed.
            now: Current time in epoch seconds.
            lease_duration: Seconds to extend the lease from ``now``.

        Returns:
            True if the claim still owns its step and the lease was extended;
            False if the claim was fenced and the attempt must be abandoned.
        """
        ...

    async def commit(
        self, claim: Claim, completion: StepCompletion, now: float
    ) -> None:
        """Atomically apply the outcome of a claimed attempt.

        Args:
            claim: The claim being committed.
            completion: The outcome to apply.
            now: Current time in epoch seconds.

        Raises:
            StaleClaimError: If the claim was fenced and must be discarded.
        """
        ...

    async def release_claim(
        self,
        claim: Claim,
        *,
        status: StepStatus,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
        now: float,
    ) -> None:
        """Return a claimed step without committing any state.

        Args:
            claim: The claim being released.
            status: The step status to record, e.g. READY or CANCELLED.
            events: History events to append.
            now: Current time in epoch seconds.
        """
        ...

    async def append_events(
        self,
        run_id: str,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
        now: float,
    ) -> None:
        """Append evidence events outside a fenced commit.

        Args:
            run_id: The owning run.
            events: The (type, data) pairs to append.
            now: Current time in epoch seconds.
        """
        ...

    async def request_cancel(self, run_id: str, now: float) -> bool:
        """Record cancellation intent on a run.

        Args:
            run_id: The run to cancel.
            now: Current time in epoch seconds.

        Returns:
            True if intent was recorded on a nonterminal run.
        """
        ...

    async def control_pending(self, now: float) -> tuple[RunRecord, ...]:
        """List drained runs awaiting a control transition.

        A run is control-pending when it is nonterminal, has no claimed step,
        and either has cancellation intent or has passed its deadline.

        Args:
            now: Current time in epoch seconds.

        Returns:
            The runs awaiting finalization.
        """
        ...

    async def finalize_run(
        self,
        run_id: str,
        *,
        status: RunStatus,
        error: dict[str, Any] | None,
        event: HistoryEventType,
        now: float,
    ) -> bool:
        """Terminate a drained run and tombstone its unresolved slots.

        Args:
            run_id: The run to finalize.
            status: The terminal status to record.
            error: Error payload recorded on the run.
            event: The terminal history event type.
            now: Current time in epoch seconds.

        Returns:
            True if the run was finalized; False if it was already terminal
            or still has a claimed step.
        """
        ...

    async def recover_orphans(self, now: float, max_recoveries: int) -> int:
        """Recover claims whose lease has expired.

        A step is orphaned when it is CLAIMED and its lease lapsed at or before
        ``now``: whoever held it stopped renewing. Each orphan consumes one
        infrastructure recovery and becomes claimable again; a step over budget
        fails its run. A claim with a live lease is left alone, so a peer that
        is mid-attempt is never disturbed.

        Args:
            now: Current time in epoch seconds.
            max_recoveries: Recovery budget per logical step.

        Returns:
            The number of steps transitioned.
        """
        ...

    async def get_run(self, run_id: str) -> RunRecord | None:
        """Load one run record.

        Args:
            run_id: The run identity.

        Returns:
            The record, or None if unknown.
        """
        ...

    async def get_steps(self, run_id: str) -> tuple[StepRecord, ...]:
        """Load a run's mailbox slots in ordinal order.

        Args:
            run_id: The run identity.

        Returns:
            The step records.
        """
        ...

    async def get_history(self, run_id: str) -> tuple[HistoryEvent, ...]:
        """Load a run's append-only history in sequence order.

        Args:
            run_id: The run identity.

        Returns:
            The history events.
        """
        ...

    async def next_due(self, now: float) -> float | None:
        """Earliest future time any runnable run becomes claimable.

        Args:
            now: Current time in epoch seconds.

        Returns:
            The epoch time, or None when no future work is scheduled.
        """
        ...


def _run_is_runnable(run: RunRecord, now: float) -> bool:
    """Whether a run may have its frontier claimed right now.

    Args:
        run: The run record.
        now: Current time in epoch seconds.

    Returns:
        True when the run is nonterminal, unsuspended, has no cancellation
        intent, and has not passed its deadline.
    """
    return (
        run.status not in TERMINAL_RUN_STATUSES
        and run.status is not RunStatus.NEEDS_ATTENTION
        and not run.cancel_requested
        and (run.deadline is None or run.deadline > now)
    )


def _lease_expired(step: StepRecord, now: float) -> bool:
    """Whether a claimed step's lease has lapsed and it may be recovered.

    Args:
        step: The step record.
        now: Current time in epoch seconds.

    Returns:
        True when the step is claimed and its lease expired at or before now.
    """
    return step.status is StepStatus.CLAIMED and step.lease_expires_at <= now


def _frontier(steps: Iterable[StepRecord]) -> StepRecord | None:
    """Find the lowest-ordinal unresolved step.

    Args:
        steps: The run's steps in ordinal order.

    Returns:
        The frontier step, or None when every slot is resolved.
    """
    for step in steps:
        if step.status not in TERMINAL_STEP_STATUSES:
            return step
    return None


class MemoryRunStore:
    """In-memory run store for tests and the workflow test harness."""

    def __init__(self):
        """Initialize empty storage."""
        self._lock = asyncio.Lock()
        self._runs: dict[str, RunRecord] = {}
        self._steps: dict[str, list[StepRecord]] = {}
        self._history: dict[str, list[HistoryEvent]] = {}
        self._dedupe: dict[tuple[str, str], str] = {}

    def _append_events(
        self,
        run_id: str,
        events: Iterable[tuple[HistoryEventType, dict[str, Any]]],
        now: float,
    ) -> None:
        """Append history events with store-assigned sequence numbers.

        Args:
            run_id: The owning run.
            events: The (type, data) pairs to append.
            now: Current time in epoch seconds.
        """
        history = self._history.setdefault(run_id, [])
        for event_type, data in events:
            history.append(
                HistoryEvent(
                    run_id=run_id,
                    seq=len(history) + 1,
                    type=event_type,
                    at=now,
                    data=data,
                )
            )

    async def admit(
        self,
        run: RunRecord,
        root_step: StepRecord,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
    ) -> tuple[bool, str]:
        """Atomically admit a run, deduplicating on the request key.

        Args:
            run: The run record to create.
            root_step: The preallocated root mailbox slot.
            events: History events to append on creation.

        Returns:
            Whether the run was created, and the authoritative run id.
        """
        async with self._lock:
            if run.request_key is not None:
                dedupe_key = (run.workflow_id, run.request_key)
                existing = self._dedupe.get(dedupe_key)
                if existing is not None:
                    return False, existing
                self._dedupe[dedupe_key] = run.run_id
            self._runs[run.run_id] = run
            self._steps[run.run_id] = [root_step]
            self._append_events(run.run_id, events, run.created_at)
            return True, run.run_id

    async def claim_next(
        self, now: float, *, lease_duration: float = DEFAULT_LEASE_DURATION
    ) -> Claim | None:
        """Claim the due frontier step of some runnable run.

        Args:
            now: Current time in epoch seconds.
            lease_duration: Seconds of renewal silence tolerated before the
                claim is treated as orphaned.

        Returns:
            A fenced claim, or None when nothing is claimable right now.
        """
        async with self._lock:
            for run in self._runs.values():
                if not _run_is_runnable(run, now):
                    continue
                steps = self._steps[run.run_id]
                frontier = _frontier(steps)
                if (
                    frontier is None
                    or frontier.status not in CLAIMABLE_STEP_STATUSES
                    or frontier.due_at > now
                ):
                    continue
                claimed = dataclasses.replace(
                    frontier,
                    status=StepStatus.CLAIMED,
                    epoch=frontier.epoch + 1,
                    lease_expires_at=now + lease_duration,
                    updated_at=now,
                )
                steps[claimed.ordinal] = claimed
                running = dataclasses.replace(
                    run, status=RunStatus.RUNNING, updated_at=now
                )
                self._runs[run.run_id] = running
                return Claim(run=running, step=claimed)
            return None

    def _check_claim(self, claim: Claim) -> tuple[RunRecord, list[StepRecord]]:
        """Validate that a claim still owns its step and state version.

        Args:
            claim: The claim to validate.

        Returns:
            The current run record and step list.

        Raises:
            StaleClaimError: If the claim was fenced.
        """
        run = self._runs.get(claim.run.run_id)
        steps = self._steps.get(claim.run.run_id)
        if run is None or steps is None:
            msg = f"Run {claim.run.run_id} no longer exists."
            raise StaleClaimError(msg)
        current = steps[claim.step.ordinal]
        if (
            current.status is not StepStatus.CLAIMED
            or current.epoch != claim.step.epoch
            or run.state_version != claim.run.state_version
        ):
            msg = (
                f"Claim on run {run.run_id} step {current.ordinal} was fenced "
                f"(epoch {claim.step.epoch} vs {current.epoch})."
            )
            raise StaleClaimError(msg)
        return run, steps

    async def renew_lease(
        self,
        claim: Claim,
        now: float,
        *,
        lease_duration: float = DEFAULT_LEASE_DURATION,
    ) -> bool:
        """Extend a live claim's lease without transitioning the step.

        Args:
            claim: The claim being renewed.
            now: Current time in epoch seconds.
            lease_duration: Seconds to extend the lease from ``now``.

        Returns:
            True if the claim still owns its step; False if it was fenced.
        """
        async with self._lock:
            try:
                _, steps = self._check_claim(claim)
            except StaleClaimError:
                return False
            step = steps[claim.step.ordinal]
            steps[step.ordinal] = dataclasses.replace(
                step, lease_expires_at=now + lease_duration
            )
            return True

    async def commit(
        self, claim: Claim, completion: StepCompletion, now: float
    ) -> None:
        """Atomically apply the outcome of a claimed attempt.

        Args:
            claim: The claim being committed.
            completion: The outcome to apply.
            now: Current time in epoch seconds.
        """
        async with self._lock:
            run, steps = self._check_claim(claim)
            step = steps[claim.step.ordinal]
            steps[step.ordinal] = dataclasses.replace(
                step,
                status=completion.step_status,
                attempts=step.attempts + (1 if completion.consume_attempt else 0),
                due_at=completion.due_at if completion.due_at is not None else 0.0,
                lease_expires_at=0.0,
                error=completion.step_error,
                updated_at=now,
            )
            for ordinal in completion.tombstones:
                slot = steps[ordinal]
                if slot.status not in TERMINAL_STEP_STATUSES:
                    steps[ordinal] = dataclasses.replace(
                        slot, status=StepStatus.CANCELLED, updated_at=now
                    )
            steps.extend(completion.new_steps)
            self._runs[run.run_id] = dataclasses.replace(
                run,
                status=completion.run_status,
                state=completion.state if completion.state is not None else run.state,
                state_version=run.state_version
                + (1 if completion.state is not None else 0),
                next_ordinal=(
                    completion.next_ordinal
                    if completion.next_ordinal is not None
                    else run.next_ordinal
                ),
                result=completion.result
                if completion.result is not None
                else run.result,
                error=completion.run_error,
                updated_at=now,
            )
            self._append_events(run.run_id, completion.events, now)

    async def release_claim(
        self,
        claim: Claim,
        *,
        status: StepStatus,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
        now: float,
    ) -> None:
        """Return a claimed step without committing any state.

        Args:
            claim: The claim being released.
            status: The step status to record.
            events: History events to append.
            now: Current time in epoch seconds.
        """
        async with self._lock:
            try:
                run, steps = self._check_claim(claim)
            except StaleClaimError:
                return
            step = steps[claim.step.ordinal]
            steps[step.ordinal] = dataclasses.replace(
                step, status=status, lease_expires_at=0.0, updated_at=now
            )
            self._append_events(run.run_id, events, now)

    async def append_events(
        self,
        run_id: str,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
        now: float,
    ) -> None:
        """Append evidence events outside a fenced commit.

        Args:
            run_id: The owning run.
            events: The (type, data) pairs to append.
            now: Current time in epoch seconds.
        """
        async with self._lock:
            self._append_events(run_id, events, now)

    async def request_cancel(self, run_id: str, now: float) -> bool:
        """Record cancellation intent on a run.

        Args:
            run_id: The run to cancel.
            now: Current time in epoch seconds.

        Returns:
            True if intent was recorded on a nonterminal run.
        """
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None or run.status in TERMINAL_RUN_STATUSES:
                return False
            self._runs[run_id] = dataclasses.replace(
                run,
                cancel_requested=True,
                status=RunStatus.CANCELLING,
                updated_at=now,
            )
            self._append_events(
                run_id, ((HistoryEventType.RUN_CANCEL_REQUESTED, {}),), now
            )
            return True

    async def control_pending(self, now: float) -> tuple[RunRecord, ...]:
        """List drained runs awaiting a control transition.

        Args:
            now: Current time in epoch seconds.

        Returns:
            The runs awaiting finalization.
        """
        async with self._lock:
            pending = []
            for run in self._runs.values():
                if run.status in TERMINAL_RUN_STATUSES:
                    continue
                if not (
                    run.cancel_requested
                    or (run.deadline is not None and run.deadline <= now)
                ):
                    continue
                if any(
                    step.status is StepStatus.CLAIMED
                    for step in self._steps[run.run_id]
                ):
                    continue
                pending.append(run)
            return tuple(pending)

    async def finalize_run(
        self,
        run_id: str,
        *,
        status: RunStatus,
        error: dict[str, Any] | None,
        event: HistoryEventType,
        now: float,
    ) -> bool:
        """Terminate a drained run and tombstone its unresolved slots.

        Args:
            run_id: The run to finalize.
            status: The terminal status to record.
            error: Error payload recorded on the run.
            event: The terminal history event type.
            now: Current time in epoch seconds.

        Returns:
            True if the run was finalized.
        """
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None or run.status in TERMINAL_RUN_STATUSES:
                return False
            steps = self._steps[run_id]
            if any(step.status is StepStatus.CLAIMED for step in steps):
                return False
            events: list[tuple[HistoryEventType, dict[str, Any]]] = []
            for step in list(steps):
                if step.status not in TERMINAL_STEP_STATUSES:
                    steps[step.ordinal] = dataclasses.replace(
                        step, status=StepStatus.CANCELLED, updated_at=now
                    )
                    events.append((
                        HistoryEventType.STEP_TOMBSTONED,
                        {"ordinal": step.ordinal},
                    ))
            self._runs[run_id] = dataclasses.replace(
                run, status=status, error=error, updated_at=now
            )
            events.append((event, {} if error is None else dict(error)))
            self._append_events(run_id, events, now)
            return True

    async def recover_orphans(self, now: float, max_recoveries: int) -> int:
        """Recover steps left claimed by a previous process.

        Args:
            now: Current time in epoch seconds.
            max_recoveries: Recovery budget per logical step.

        Returns:
            The number of steps transitioned.
        """
        async with self._lock:
            recovered = 0
            for run in list(self._runs.values()):
                if run.status in TERMINAL_RUN_STATUSES:
                    continue
                steps = self._steps[run.run_id]
                for step in list(steps):
                    if not _lease_expired(step, now):
                        continue
                    recovered += 1
                    if step.recoveries + 1 > max_recoveries:
                        steps[step.ordinal] = dataclasses.replace(
                            step,
                            status=StepStatus.FAILED,
                            recoveries=step.recoveries + 1,
                            lease_expires_at=0.0,
                            error={"reason": "recovery_budget_exhausted"},
                            updated_at=now,
                        )
                        self._runs[run.run_id] = dataclasses.replace(
                            run,
                            status=RunStatus.FAILED,
                            error={"reason": "recovery_budget_exhausted"},
                            updated_at=now,
                        )
                        self._append_events(
                            run.run_id,
                            (
                                (
                                    HistoryEventType.RUN_FAILED,
                                    {"reason": "recovery_budget_exhausted"},
                                ),
                            ),
                            now,
                        )
                    else:
                        steps[step.ordinal] = dataclasses.replace(
                            step,
                            status=StepStatus.RECOVERY_WAIT,
                            recoveries=step.recoveries + 1,
                            due_at=now,
                            lease_expires_at=0.0,
                            updated_at=now,
                        )
                        self._append_events(
                            run.run_id,
                            (
                                (
                                    HistoryEventType.STEP_RECOVERED,
                                    {"ordinal": step.ordinal},
                                ),
                            ),
                            now,
                        )
            return recovered

    async def get_run(self, run_id: str) -> RunRecord | None:
        """Load one run record.

        Args:
            run_id: The run identity.

        Returns:
            The record, or None if unknown.
        """
        async with self._lock:
            return self._runs.get(run_id)

    async def get_steps(self, run_id: str) -> tuple[StepRecord, ...]:
        """Load a run's mailbox slots in ordinal order.

        Args:
            run_id: The run identity.

        Returns:
            The step records.
        """
        async with self._lock:
            return tuple(self._steps.get(run_id, ()))

    async def get_history(self, run_id: str) -> tuple[HistoryEvent, ...]:
        """Load a run's append-only history in sequence order.

        Args:
            run_id: The run identity.

        Returns:
            The history events.
        """
        async with self._lock:
            return tuple(self._history.get(run_id, ()))

    async def next_due(self, now: float) -> float | None:
        """Earliest future time any runnable run becomes claimable.

        Args:
            now: Current time in epoch seconds.

        Returns:
            The epoch time, or None when no future work is scheduled.
        """
        async with self._lock:
            due_times = []
            for run in self._runs.values():
                if not _run_is_runnable(run, now):
                    continue
                frontier = _frontier(self._steps[run.run_id])
                if frontier is not None and frontier.status in CLAIMABLE_STEP_STATUSES:
                    due_times.append(frontier.due_at)
            return min(due_times) if due_times else None


_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_runs (
    run_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    definition_digest TEXT NOT NULL,
    status TEXT NOT NULL,
    state TEXT NOT NULL,
    state_version INTEGER NOT NULL,
    next_ordinal INTEGER NOT NULL,
    result TEXT,
    error TEXT,
    request_key TEXT,
    labels TEXT,
    deadline REAL,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_steps (
    run_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    handler_id TEXT NOT NULL,
    status TEXT NOT NULL,
    args TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    recoveries INTEGER NOT NULL DEFAULT 0,
    due_at REAL NOT NULL DEFAULT 0,
    epoch INTEGER NOT NULL DEFAULT 0,
    lease_expires_at REAL NOT NULL DEFAULT 0,
    error TEXT,
    origin TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (run_id, ordinal)
);
CREATE TABLE IF NOT EXISTS workflow_history (
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    type TEXT NOT NULL,
    at REAL NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (run_id, seq)
);
CREATE TABLE IF NOT EXISTS workflow_dedupe (
    workflow_id TEXT NOT NULL,
    request_key TEXT NOT NULL,
    run_id TEXT NOT NULL,
    PRIMARY KEY (workflow_id, request_key)
);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs (status);
"""

_STEP_MIGRATIONS: Final = (
    (
        "lease_expires_at",
        "ALTER TABLE workflow_steps ADD COLUMN lease_expires_at REAL NOT NULL DEFAULT 0",
    ),
)


def _dump(value: Any) -> str | None:
    """Serialize an optional JSON payload column.

    Args:
        value: The JSON-compatible value.

    Returns:
        The JSON text, or None.
    """
    return None if value is None else json.dumps(value)


def _load(text: str | None) -> Any:
    """Deserialize an optional JSON payload column.

    Args:
        text: The JSON text, or None.

    Returns:
        The decoded value, or None.
    """
    return None if text is None else json.loads(text)


def _run_from_row(row: sqlite3.Row) -> RunRecord:
    """Build a run record from a database row.

    Args:
        row: The ``workflow_runs`` row.

    Returns:
        The run record.
    """
    return RunRecord(
        run_id=row["run_id"],
        workflow_id=row["workflow_id"],
        definition_digest=row["definition_digest"],
        status=RunStatus(row["status"]),
        state=json.loads(row["state"]),
        state_version=row["state_version"],
        next_ordinal=row["next_ordinal"],
        result=_load(row["result"]),
        error=_load(row["error"]),
        request_key=row["request_key"],
        labels=_load(row["labels"]),
        deadline=row["deadline"],
        cancel_requested=bool(row["cancel_requested"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _step_from_row(row: sqlite3.Row) -> StepRecord:
    """Build a step record from a database row.

    Args:
        row: The ``workflow_steps`` row.

    Returns:
        The step record.
    """
    return StepRecord(
        run_id=row["run_id"],
        ordinal=row["ordinal"],
        handler_id=row["handler_id"],
        status=StepStatus(row["status"]),
        args=json.loads(row["args"]),
        attempts=row["attempts"],
        recoveries=row["recoveries"],
        due_at=row["due_at"],
        epoch=row["epoch"],
        lease_expires_at=row["lease_expires_at"],
        error=_load(row["error"]),
        origin=row["origin"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SqliteRunStore:
    """Crash-safe run store backed by a local SQLite database."""

    def __init__(self, db_path: str | Path):
        """Open (and create if needed) the backing database.

        Args:
            db_path: Path to the SQLite database file.
        """
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.isolation_level = None
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.executescript(_SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Add columns and indexes missing from databases created by older versions.

        The check and the alter run in one immediate transaction so two
        processes opening the same file cannot both attempt it. Rows predating
        a column take its default, which for ``lease_expires_at`` means an
        already-lapsed lease: a step left claimed by the previous binary is a
        genuine orphan and is recovered on the first recovery pass.
        """
        self._db.execute("BEGIN IMMEDIATE")
        try:
            columns = {
                row["name"]
                for row in self._db.execute("PRAGMA table_info(workflow_steps)")
            }
            for name, statement in _STEP_MIGRATIONS:
                if name not in columns:
                    self._db.execute(statement)
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_workflow_steps_lease"
                " ON workflow_steps (status, lease_expires_at)"
            )
            self._db.execute("COMMIT")
        except BaseException:
            self._db.execute("ROLLBACK")
            raise

    def close(self) -> None:
        """Close the backing database connection."""
        self._db.close()

    def _append_events(
        self,
        run_id: str,
        events: Iterable[tuple[HistoryEventType, dict[str, Any]]],
        now: float,
    ) -> None:
        """Append history events inside the current transaction.

        Args:
            run_id: The owning run.
            events: The (type, data) pairs to append.
            now: Current time in epoch seconds.
        """
        row = self._db.execute(
            "SELECT COALESCE(MAX(seq), 0) AS seq FROM workflow_history WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        seq = row["seq"]
        for event_type, data in events:
            seq += 1
            self._db.execute(
                "INSERT INTO workflow_history (run_id, seq, type, at, data)"
                " VALUES (?, ?, ?, ?, ?)",
                (run_id, seq, event_type.value, now, json.dumps(data)),
            )

    def _insert_step(self, step: StepRecord) -> None:
        """Insert a step row inside the current transaction.

        Args:
            step: The step record.
        """
        self._db.execute(
            "INSERT INTO workflow_steps (run_id, ordinal, handler_id, status, args,"
            " attempts, recoveries, due_at, epoch, lease_expires_at, error, origin,"
            " created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                step.run_id,
                step.ordinal,
                step.handler_id,
                step.status.value,
                json.dumps(step.args),
                step.attempts,
                step.recoveries,
                step.due_at,
                step.epoch,
                step.lease_expires_at,
                _dump(step.error),
                step.origin,
                step.created_at,
                step.updated_at,
            ),
        )

    def _load_steps(self, run_id: str) -> list[StepRecord]:
        """Load a run's steps in ordinal order inside the current transaction.

        Args:
            run_id: The owning run.

        Returns:
            The step records.
        """
        rows = self._db.execute(
            "SELECT * FROM workflow_steps WHERE run_id = ? ORDER BY ordinal",
            (run_id,),
        ).fetchall()
        return [_step_from_row(row) for row in rows]

    async def admit(
        self,
        run: RunRecord,
        root_step: StepRecord,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
    ) -> tuple[bool, str]:
        """Atomically admit a run, deduplicating on the request key.

        Args:
            run: The run record to create.
            root_step: The preallocated root mailbox slot.
            events: History events to append on creation.

        Returns:
            Whether the run was created, and the authoritative run id.
        """
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                if run.request_key is not None:
                    row = self._db.execute(
                        "SELECT run_id FROM workflow_dedupe"
                        " WHERE workflow_id = ? AND request_key = ?",
                        (run.workflow_id, run.request_key),
                    ).fetchone()
                    if row is not None:
                        self._db.execute("ROLLBACK")
                        return False, row["run_id"]
                    self._db.execute(
                        "INSERT INTO workflow_dedupe (workflow_id, request_key, run_id)"
                        " VALUES (?, ?, ?)",
                        (run.workflow_id, run.request_key, run.run_id),
                    )
                self._db.execute(
                    "INSERT INTO workflow_runs (run_id, workflow_id,"
                    " definition_digest, status, state, state_version, next_ordinal,"
                    " result, error, request_key, labels, deadline, cancel_requested,"
                    " created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        run.run_id,
                        run.workflow_id,
                        run.definition_digest,
                        run.status.value,
                        json.dumps(run.state),
                        run.state_version,
                        run.next_ordinal,
                        _dump(run.result),
                        _dump(run.error),
                        run.request_key,
                        _dump(run.labels),
                        run.deadline,
                        int(run.cancel_requested),
                        run.created_at,
                        run.updated_at,
                    ),
                )
                self._insert_step(root_step)
                self._append_events(run.run_id, events, run.created_at)
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            return True, run.run_id

    async def claim_next(
        self, now: float, *, lease_duration: float = DEFAULT_LEASE_DURATION
    ) -> Claim | None:
        """Claim the due frontier step of some runnable run.

        Args:
            now: Current time in epoch seconds.
            lease_duration: Seconds of renewal silence tolerated before the
                claim is treated as orphaned.

        Returns:
            A fenced claim, or None when nothing is claimable right now.
        """
        terminal = tuple(s.value for s in TERMINAL_RUN_STATUSES)
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            claim = None
            try:
                rows = self._db.execute(
                    "SELECT * FROM workflow_runs WHERE status NOT IN"
                    f" ({','.join('?' * len(terminal))})"
                    " AND status != ? AND cancel_requested = 0"
                    " AND (deadline IS NULL OR deadline > ?)"
                    " ORDER BY created_at",
                    (*terminal, RunStatus.NEEDS_ATTENTION.value, now),
                ).fetchall()
                for row in rows:
                    run = _run_from_row(row)
                    frontier = _frontier(self._load_steps(run.run_id))
                    if (
                        frontier is None
                        or frontier.status not in CLAIMABLE_STEP_STATUSES
                        or frontier.due_at > now
                    ):
                        continue
                    claimed = dataclasses.replace(
                        frontier,
                        status=StepStatus.CLAIMED,
                        epoch=frontier.epoch + 1,
                        lease_expires_at=now + lease_duration,
                        updated_at=now,
                    )
                    self._db.execute(
                        "UPDATE workflow_steps SET status = ?, epoch = ?,"
                        " lease_expires_at = ?, updated_at = ?"
                        " WHERE run_id = ? AND ordinal = ?",
                        (
                            claimed.status.value,
                            claimed.epoch,
                            claimed.lease_expires_at,
                            now,
                            claimed.run_id,
                            claimed.ordinal,
                        ),
                    )
                    self._db.execute(
                        "UPDATE workflow_runs SET status = ?, updated_at = ?"
                        " WHERE run_id = ?",
                        (RunStatus.RUNNING.value, now, run.run_id),
                    )
                    running = dataclasses.replace(
                        run, status=RunStatus.RUNNING, updated_at=now
                    )
                    claim = Claim(run=running, step=claimed)
                    break
                self._db.execute("COMMIT" if claim is not None else "ROLLBACK")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            return claim

    def _check_claim(self, claim: Claim) -> None:
        """Validate that a claim still owns its step and state version.

        Args:
            claim: The claim to validate.

        Raises:
            StaleClaimError: If the claim was fenced.
        """
        row = self._db.execute(
            "SELECT s.status AS step_status, s.epoch AS epoch,"
            " r.state_version AS state_version"
            " FROM workflow_steps s JOIN workflow_runs r ON r.run_id = s.run_id"
            " WHERE s.run_id = ? AND s.ordinal = ?",
            (claim.run.run_id, claim.step.ordinal),
        ).fetchone()
        if (
            row is None
            or row["step_status"] != StepStatus.CLAIMED.value
            or row["epoch"] != claim.step.epoch
            or row["state_version"] != claim.run.state_version
        ):
            msg = (
                f"Claim on run {claim.run.run_id} step {claim.step.ordinal} was fenced."
            )
            raise StaleClaimError(msg)

    async def renew_lease(
        self,
        claim: Claim,
        now: float,
        *,
        lease_duration: float = DEFAULT_LEASE_DURATION,
    ) -> bool:
        """Extend a live claim's lease without transitioning the step.

        Args:
            claim: The claim being renewed.
            now: Current time in epoch seconds.
            lease_duration: Seconds to extend the lease from ``now``.

        Returns:
            True if the claim still owns its step; False if it was fenced.
        """
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                try:
                    self._check_claim(claim)
                except StaleClaimError:
                    self._db.execute("ROLLBACK")
                    return False
                self._db.execute(
                    "UPDATE workflow_steps SET lease_expires_at = ?"
                    " WHERE run_id = ? AND ordinal = ?",
                    (now + lease_duration, claim.run.run_id, claim.step.ordinal),
                )
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            return True

    async def commit(
        self, claim: Claim, completion: StepCompletion, now: float
    ) -> None:
        """Atomically apply the outcome of a claimed attempt.

        Args:
            claim: The claim being committed.
            completion: The outcome to apply.
            now: Current time in epoch seconds.
        """
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._check_claim(claim)
                self._db.execute(
                    "UPDATE workflow_steps SET status = ?, attempts = attempts + ?,"
                    " due_at = ?, lease_expires_at = 0, error = ?, updated_at = ?"
                    " WHERE run_id = ? AND ordinal = ?",
                    (
                        completion.step_status.value,
                        1 if completion.consume_attempt else 0,
                        completion.due_at if completion.due_at is not None else 0.0,
                        _dump(completion.step_error),
                        now,
                        claim.run.run_id,
                        claim.step.ordinal,
                    ),
                )
                if completion.tombstones:
                    terminal = tuple(s.value for s in TERMINAL_STEP_STATUSES)
                    self._db.execute(
                        "UPDATE workflow_steps SET status = ?, updated_at = ?"
                        f" WHERE run_id = ? AND ordinal IN"
                        f" ({','.join('?' * len(completion.tombstones))})"
                        f" AND status NOT IN ({','.join('?' * len(terminal))})",
                        (
                            StepStatus.CANCELLED.value,
                            now,
                            claim.run.run_id,
                            *completion.tombstones,
                            *terminal,
                        ),
                    )
                for step in completion.new_steps:
                    self._insert_step(step)
                self._db.execute(
                    "UPDATE workflow_runs SET status = ?,"
                    " state = CASE WHEN ? THEN ? ELSE state END,"
                    " state_version = state_version + ?,"
                    " next_ordinal = COALESCE(?, next_ordinal),"
                    " result = COALESCE(?, result), error = ?, updated_at = ?"
                    " WHERE run_id = ?",
                    (
                        completion.run_status.value,
                        completion.state is not None,
                        _dump(completion.state),
                        1 if completion.state is not None else 0,
                        completion.next_ordinal,
                        _dump(completion.result),
                        _dump(completion.run_error),
                        now,
                        claim.run.run_id,
                    ),
                )
                self._append_events(claim.run.run_id, completion.events, now)
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    async def release_claim(
        self,
        claim: Claim,
        *,
        status: StepStatus,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
        now: float,
    ) -> None:
        """Return a claimed step without committing any state.

        Args:
            claim: The claim being released.
            status: The step status to record.
            events: History events to append.
            now: Current time in epoch seconds.
        """
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                try:
                    self._check_claim(claim)
                except StaleClaimError:
                    self._db.execute("ROLLBACK")
                    return
                self._db.execute(
                    "UPDATE workflow_steps SET status = ?, lease_expires_at = 0,"
                    " updated_at = ? WHERE run_id = ? AND ordinal = ?",
                    (status.value, now, claim.run.run_id, claim.step.ordinal),
                )
                self._append_events(claim.run.run_id, events, now)
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    async def append_events(
        self,
        run_id: str,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
        now: float,
    ) -> None:
        """Append evidence events outside a fenced commit.

        Args:
            run_id: The owning run.
            events: The (type, data) pairs to append.
            now: Current time in epoch seconds.
        """
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                self._append_events(run_id, events, now)
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    async def request_cancel(self, run_id: str, now: float) -> bool:
        """Record cancellation intent on a run.

        Args:
            run_id: The run to cancel.
            now: Current time in epoch seconds.

        Returns:
            True if intent was recorded on a nonterminal run.
        """
        terminal = tuple(s.value for s in TERMINAL_RUN_STATUSES)
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                cursor = self._db.execute(
                    "UPDATE workflow_runs SET cancel_requested = 1, status = ?,"
                    " updated_at = ? WHERE run_id = ? AND status NOT IN"
                    f" ({','.join('?' * len(terminal))})",
                    (RunStatus.CANCELLING.value, now, run_id, *terminal),
                )
                if cursor.rowcount == 0:
                    self._db.execute("ROLLBACK")
                    return False
                self._append_events(
                    run_id, ((HistoryEventType.RUN_CANCEL_REQUESTED, {}),), now
                )
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            return True

    async def control_pending(self, now: float) -> tuple[RunRecord, ...]:
        """List drained runs awaiting a control transition.

        Args:
            now: Current time in epoch seconds.

        Returns:
            The runs awaiting finalization.
        """
        terminal = tuple(s.value for s in TERMINAL_RUN_STATUSES)
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM workflow_runs r WHERE status NOT IN"
                f" ({','.join('?' * len(terminal))})"
                " AND (cancel_requested = 1 OR (deadline IS NOT NULL AND deadline <= ?))"
                " AND NOT EXISTS (SELECT 1 FROM workflow_steps s"
                " WHERE s.run_id = r.run_id AND s.status = ?)",
                (*terminal, now, StepStatus.CLAIMED.value),
            ).fetchall()
            return tuple(_run_from_row(row) for row in rows)

    async def finalize_run(
        self,
        run_id: str,
        *,
        status: RunStatus,
        error: dict[str, Any] | None,
        event: HistoryEventType,
        now: float,
    ) -> bool:
        """Terminate a drained run and tombstone its unresolved slots.

        Args:
            run_id: The run to finalize.
            status: The terminal status to record.
            error: Error payload recorded on the run.
            event: The terminal history event type.
            now: Current time in epoch seconds.

        Returns:
            True if the run was finalized.
        """
        terminal_run = tuple(s.value for s in TERMINAL_RUN_STATUSES)
        terminal_step = tuple(s.value for s in TERMINAL_STEP_STATUSES)
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row = self._db.execute(
                    "SELECT status FROM workflow_runs WHERE run_id = ?", (run_id,)
                ).fetchone()
                if row is None or row["status"] in terminal_run:
                    self._db.execute("ROLLBACK")
                    return False
                claimed = self._db.execute(
                    "SELECT 1 FROM workflow_steps WHERE run_id = ? AND status = ?",
                    (run_id, StepStatus.CLAIMED.value),
                ).fetchone()
                if claimed is not None:
                    self._db.execute("ROLLBACK")
                    return False
                open_rows = self._db.execute(
                    "SELECT ordinal FROM workflow_steps WHERE run_id = ?"
                    f" AND status NOT IN ({','.join('?' * len(terminal_step))})"
                    " ORDER BY ordinal",
                    (run_id, *terminal_step),
                ).fetchall()
                self._db.execute(
                    "UPDATE workflow_steps SET status = ?, updated_at = ?"
                    f" WHERE run_id = ? AND status NOT IN"
                    f" ({','.join('?' * len(terminal_step))})",
                    (StepStatus.CANCELLED.value, now, run_id, *terminal_step),
                )
                self._db.execute(
                    "UPDATE workflow_runs SET status = ?, error = ?, updated_at = ?"
                    " WHERE run_id = ?",
                    (status.value, _dump(error), now, run_id),
                )
                events: list[tuple[HistoryEventType, dict[str, Any]]] = [
                    (HistoryEventType.STEP_TOMBSTONED, {"ordinal": row["ordinal"]})
                    for row in open_rows
                ]
                events.append((event, {} if error is None else dict(error)))
                self._append_events(run_id, events, now)
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            return True

    async def recover_orphans(self, now: float, max_recoveries: int) -> int:
        """Recover steps left claimed by a previous process.

        Args:
            now: Current time in epoch seconds.
            max_recoveries: Recovery budget per logical step.

        Returns:
            The number of steps transitioned.
        """
        terminal = tuple(s.value for s in TERMINAL_RUN_STATUSES)
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                rows = self._db.execute(
                    "SELECT s.* FROM workflow_steps s"
                    " JOIN workflow_runs r ON r.run_id = s.run_id"
                    " WHERE s.status = ? AND s.lease_expires_at <= ?"
                    f" AND r.status NOT IN ({','.join('?' * len(terminal))})",
                    (StepStatus.CLAIMED.value, now, *terminal),
                ).fetchall()
                recovered = 0
                for row in rows:
                    step = _step_from_row(row)
                    recovered += 1
                    if step.recoveries + 1 > max_recoveries:
                        self._db.execute(
                            "UPDATE workflow_steps SET status = ?, recoveries = ?,"
                            " lease_expires_at = 0, error = ?, updated_at = ?"
                            " WHERE run_id = ? AND ordinal = ?",
                            (
                                StepStatus.FAILED.value,
                                step.recoveries + 1,
                                json.dumps({"reason": "recovery_budget_exhausted"}),
                                now,
                                step.run_id,
                                step.ordinal,
                            ),
                        )
                        self._db.execute(
                            "UPDATE workflow_runs SET status = ?, error = ?,"
                            " updated_at = ? WHERE run_id = ?",
                            (
                                RunStatus.FAILED.value,
                                json.dumps({"reason": "recovery_budget_exhausted"}),
                                now,
                                step.run_id,
                            ),
                        )
                        self._append_events(
                            step.run_id,
                            (
                                (
                                    HistoryEventType.RUN_FAILED,
                                    {"reason": "recovery_budget_exhausted"},
                                ),
                            ),
                            now,
                        )
                    else:
                        self._db.execute(
                            "UPDATE workflow_steps SET status = ?, recoveries = ?,"
                            " due_at = ?, lease_expires_at = 0, updated_at = ?"
                            " WHERE run_id = ? AND ordinal = ?",
                            (
                                StepStatus.RECOVERY_WAIT.value,
                                step.recoveries + 1,
                                now,
                                now,
                                step.run_id,
                                step.ordinal,
                            ),
                        )
                        self._append_events(
                            step.run_id,
                            (
                                (
                                    HistoryEventType.STEP_RECOVERED,
                                    {"ordinal": step.ordinal},
                                ),
                            ),
                            now,
                        )
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            return recovered

    async def get_run(self, run_id: str) -> RunRecord | None:
        """Load one run record.

        Args:
            run_id: The run identity.

        Returns:
            The record, or None if unknown.
        """
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM workflow_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            return None if row is None else _run_from_row(row)

    async def get_steps(self, run_id: str) -> tuple[StepRecord, ...]:
        """Load a run's mailbox slots in ordinal order.

        Args:
            run_id: The run identity.

        Returns:
            The step records.
        """
        with self._lock:
            return tuple(self._load_steps(run_id))

    async def get_history(self, run_id: str) -> tuple[HistoryEvent, ...]:
        """Load a run's append-only history in sequence order.

        Args:
            run_id: The run identity.

        Returns:
            The history events.
        """
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM workflow_history WHERE run_id = ? ORDER BY seq",
                (run_id,),
            ).fetchall()
            return tuple(
                HistoryEvent(
                    run_id=row["run_id"],
                    seq=row["seq"],
                    type=HistoryEventType(row["type"]),
                    at=row["at"],
                    data=json.loads(row["data"]),
                )
                for row in rows
            )

    async def next_due(self, now: float) -> float | None:
        """Earliest future time any runnable run becomes claimable.

        Args:
            now: Current time in epoch seconds.

        Returns:
            The epoch time, or None when no future work is scheduled.
        """
        terminal = tuple(s.value for s in TERMINAL_RUN_STATUSES)
        with self._lock:
            rows = self._db.execute(
                "SELECT run_id FROM workflow_runs WHERE status NOT IN"
                f" ({','.join('?' * len(terminal))})"
                " AND status != ? AND cancel_requested = 0"
                " AND (deadline IS NULL OR deadline > ?)",
                (*terminal, RunStatus.NEEDS_ATTENTION.value, now),
            ).fetchall()
            due_times = []
            for row in rows:
                frontier = _frontier(self._load_steps(row["run_id"]))
                if frontier is not None and frontier.status in CLAIMABLE_STEP_STATUSES:
                    due_times.append(frontier.due_at)
            return min(due_times) if due_times else None
