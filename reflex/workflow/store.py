"""Durable run stores for the workflow kernel.

A store is the single authority for run state: admission with idempotent
request keys, the ordered per-run mailbox, claim fencing and leasing, and the
atomic step commit that persists a state patch together with its successor
slots. The kernel decides what should happen; the store makes it durable
atomically.

``MemoryRunStore`` backs tests and the harness. ``SqliteRunStore`` provides
crash-safe persistence on a single machine using the standard library. Run
exactly one worker process per database file: its calls are synchronous on the
caller's event loop, so cross-process write contention stalls the app that is
serving requests. Contended writes are bounded to a short busy timeout and
surface as transient errors the kernel retries, rather than freezing the loop
for seconds.
"""

from __future__ import annotations

import asyncio
import copy
import dataclasses
import json
import sqlite3
import threading
from typing import TYPE_CHECKING, Any, Final, Literal, Protocol

from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import DEFAULT_LEASE_DURATION

from reflex.workflow.records import (
    TERMINAL_RUN_STATUSES,
    TERMINAL_STEP_STATUSES,
    HistoryEvent,
    HistoryEventType,
    RunQuery,
    RunRecord,
    RunStatus,
    StepRecord,
    StepStatus,
    step_claimable_at,
    step_wake_at,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


DeliveryDisposition = Literal[
    "resolved",
    "counted",
    "expired",
    "buffered",
    "duplicate",
    "unknown_run",
    "run_terminal",
]


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
        children: Child runs to create in the same transaction as this commit,
            each paired with its root slot.
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
    children: tuple[tuple[RunRecord, StepRecord], ...] = ()


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

    async def deliver(
        self,
        run_id: str,
        wait_key: str,
        dedupe_key: str,
        payload: dict[str, Any],
        now: float,
    ) -> DeliveryDisposition:
        """Deliver a payload to a run, resolving its wait or buffering it.

        The delivery and the wait contend on one row: whichever of the delivery
        and the deadline lands first flips the blocked slot and the other can
        no longer resolve it. A delivery that arrives before the run has armed
        its wait is buffered, and the arming commit consumes it atomically, so
        a fast signal is never lost.

        This path must never write ``run.state`` or ``run.state_version``: a
        delivery must not be able to fence an attempt.

        Args:
            run_id: The receiving run.
            wait_key: The address the waiting slot declared.
            dedupe_key: Sender-supplied identity, making redelivery a no-op.
            payload: JSON-compatible payload to hand the resuming handler.
            now: Current time in epoch seconds.

        Returns:
            What the store did with the delivery.
        """
        ...

    async def admit_children(
        self,
        runs: tuple[tuple[RunRecord, StepRecord], ...],
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
        now: float,
    ) -> None:
        """Create child runs, each with its root slot.

        Only ever inserts brand-new rows, so it locks no existing run and
        cannot invert lock order against a concurrent commit.

        Args:
            runs: The child run records paired with their root slots.
            events: History events to append to the parent.
            now: Current time in epoch seconds.
        """
        ...

    async def record_arrival(
        self,
        run_id: str,
        ordinal: int,
        payload: dict[str, Any],
        dedupe_key: str,
        now: float,
    ) -> DeliveryDisposition:
        """Count one arrival against a join slot.

        The counter is only ever incremented by this compare-and-swap, so a
        redelivered child result cannot be counted twice, and the slot becomes
        claimable exactly when the last expected arrival lands.

        Args:
            run_id: The waiting parent run.
            ordinal: The join slot's ordinal.
            payload: The arriving result.
            dedupe_key: Identity of the arrival.
            now: Current time in epoch seconds.

        Returns:
            ``"resolved"`` when this arrival completed the join, ``"counted"``
            when more are still expected, or why it was refused.
        """
        ...

    async def count_active(self, workflow_id: str, flow_key: str) -> int:
        """Count runs of a root still in flight under a flow-control key.

        Args:
            workflow_id: The workflow identity.
            flow_key: The computed grouping key.

        Returns:
            How many non-terminal runs share the key.
        """
        ...

    async def first_active(self, workflow_id: str, flow_key: str) -> RunRecord | None:
        """Find the oldest run still in flight under a flow-control key.

        Args:
            workflow_id: The workflow identity.
            flow_key: The computed grouping key.

        Returns:
            The run, or None when the key has no active run.
        """
        ...

    async def count_started_since(
        self, workflow_id: str, flow_key: str, since: float
    ) -> int:
        """Count runs of a root admitted under a key since a point in time.

        Args:
            workflow_id: The workflow identity.
            flow_key: The computed grouping key.
            since: Exclusive lower bound in epoch seconds.

        Returns:
            How many runs were admitted in the window.
        """
        ...

    async def nth_recent_start(
        self, workflow_id: str, flow_key: str, n: int
    ) -> float | None:
        """Find the nth most recent scheduled start under a flow key.

        Throttling has to place each new run relative to the ones already
        scheduled, not merely count them: deferring every excess start by one
        window replays the burst intact, one window later. Keeping each start
        at least a window after the nth most recent one spaces the backlog and
        holds the sliding-window limit.

        A run's scheduled start is when its root slot comes due, which for an
        undeferred run is when it was admitted.

        Args:
            workflow_id: The workflow identity.
            flow_key: The computed grouping key.
            n: How far back to look, counting from the most recent as 1.

        Returns:
            The scheduled start, or None when fewer than n runs exist.
        """
        ...

    async def defer_root(self, run_id: str, due_at: float, now: float) -> bool:
        """Push a not-yet-started run's root slot later, for debouncing.

        Args:
            run_id: The pending run.
            due_at: The new earliest start time.
            now: Current time in epoch seconds.

        Returns:
            True when the root had not started and was deferred.
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

    async def resume_run(self, run_id: str, now: float) -> bool:
        """Re-open a suspended run so its frontier step runs again.

        Suspension is an operator state, not an outcome: the run waits for a
        human to fix whatever made the outcome uncertain. Resuming clears the
        error, grants the frontier step a fresh attempt budget, and makes it
        claimable immediately.

        Args:
            run_id: The run to resume.
            now: Current time in epoch seconds.

        Returns:
            True if a suspended run was re-opened.
        """
        ...

    async def recover_orphans(
        self, now: float, max_recoveries: int
    ) -> tuple[int, tuple[str, ...]]:
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
            How many steps were transitioned, and the ids of runs this pass
            failed outright by exhausting their recovery budget -- their
            parents still need to be told.
        """
        ...

    async def list_runs(self, query: RunQuery) -> tuple[RunRecord, ...]:
        """List runs matching a query, newest first.

        Args:
            query: The filters and pagination cursor to apply.

        Returns:
            The matching run records.
        """
        ...

    async def list_children(
        self, parent_run_id: str, parent_ordinal: int
    ) -> tuple[RunRecord, ...]:
        """List the child runs admitted for one join slot.

        A decided race has to reach its losing branches, and an operator
        inspecting a fan-out wants its children without paging the whole run
        table, so this is a first-class lookup rather than a filtered listing.

        Args:
            parent_run_id: The run that fanned out.
            parent_ordinal: The join slot the children report to.

        Returns:
            The child run records, oldest first.
        """
        ...

    async def find_by_request_key(
        self, workflow_id: str, request_key: str
    ) -> str | None:
        """Find the run a request key already admitted, if any.

        Admission dedupe must be answerable before any start policy runs, so a
        provider redelivering an event cannot be treated as a new start and
        trip a singleton, throttle, or debounce against the run it should
        simply return.

        Args:
            workflow_id: The workflow identity.
            request_key: The idempotent admission key.

        Returns:
            The existing run id, or None when the key is unused.
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


def _detach_run(run: RunRecord) -> RunRecord:
    """Copy a run record's mutable payloads before handing it to a caller.

    The in-memory store would otherwise hand out live references to the values
    it is storing, so a caller mutating a returned run's state would silently
    change committed data -- behavior a database-backed store cannot have.

    Args:
        run: The stored record.

    Returns:
        A record that shares no mutable structure with the store.
    """
    return dataclasses.replace(
        run,
        state=copy.deepcopy(run.state),
        result=copy.deepcopy(run.result),
        error=copy.deepcopy(run.error),
        labels=copy.deepcopy(run.labels),
    )


def _detach_step(step: StepRecord) -> StepRecord:
    """Copy a step record's mutable payloads before handing it to a caller.

    Args:
        step: The stored record.

    Returns:
        A record that shares no mutable structure with the store.
    """
    return dataclasses.replace(
        step, args=copy.deepcopy(step.args), error=copy.deepcopy(step.error)
    )


def _matches_query(run: RunRecord, query: RunQuery) -> bool:
    """Whether a run satisfies every filter in a query.

    Args:
        run: The run record to test.
        query: The filters to apply.

    Returns:
        True when the run matches.
    """
    if query.workflow_id is not None and run.workflow_id != query.workflow_id:
        return False
    if query.statuses and run.status not in query.statuses:
        return False
    if query.created_before is not None and (run.created_at, run.run_id) >= (
        query.created_before
    ):
        return False
    labels = run.labels or {}
    return all(labels.get(key) == value for key, value in (query.labels or {}).items())


def _wait_expired(step: StepRecord, now: float) -> bool:
    """Whether a blocked wait's deadline has already won its race.

    Once the deadline falls due the timeout branch owns the slot, so a late
    delivery must be refused outright rather than buffered: buffering it would
    let a signal for an expired wait resolve a later one on the same channel.

    Args:
        step: The frontier slot.
        now: Current time in epoch seconds.

    Returns:
        True when the wait has already timed out.
    """
    return step.status is StepStatus.BLOCKED and 0.0 < step.due_at <= now


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
        self._inbox: dict[str, dict[tuple[str, str, str], bool]] = {}
        self._pending: dict[str, dict[str, list[dict[str, Any]]]] = {}

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
                if frontier is None or not step_claimable_at(frontier, now):
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

    def _arm(self, step: StepRecord, now: float) -> StepRecord:
        """Resolve a newly armed wait against an already-buffered delivery.

        A signal that arrives before the run reaches its wait is buffered, so
        arming must consume it in the same commit; otherwise a fast sender
        would block the run forever.

        Args:
            step: The slot being appended.
            now: Current time in epoch seconds.

        Returns:
            The slot, already resolved when a matching delivery was waiting.
        """
        if step.status is not StepStatus.BLOCKED or step.wait_key is None:
            return step
        queued = self._pending.get(step.run_id, {}).get(step.wait_key)
        if not queued:
            return step
        buffered = queued.pop(0)
        return dataclasses.replace(
            step,
            status=StepStatus.READY,
            due_at=now,
            args={**step.args, "__payload__": buffered},
            updated_at=now,
        )

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
            for new_step in completion.new_steps:
                steps.append(self._arm(new_step, now))
            for child_run, child_step in completion.children:
                self._runs[child_run.run_id] = child_run
                self._steps[child_run.run_id] = [child_step]
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

    async def deliver(
        self,
        run_id: str,
        wait_key: str,
        dedupe_key: str,
        payload: dict[str, Any],
        now: float,
    ) -> DeliveryDisposition:
        """Deliver a payload to a run, resolving its wait or buffering it.

        Args:
            run_id: The receiving run.
            wait_key: The address the waiting slot declared.
            dedupe_key: Sender-supplied identity, making redelivery a no-op.
            payload: JSON-compatible payload to hand the resuming handler.
            now: Current time in epoch seconds.

        Returns:
            What the store did with the delivery.
        """
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return "unknown_run"
            if run.status in TERMINAL_RUN_STATUSES:
                return "run_terminal"
            inbox = self._inbox.setdefault(run_id, {})
            if (run_id, wait_key, dedupe_key) in inbox:
                return "duplicate"
            inbox[run_id, wait_key, dedupe_key] = True
            steps = self._steps[run_id]
            frontier = _frontier(steps)
            if frontier is not None and _wait_expired(frontier, now):
                return "expired"
            if (
                frontier is not None
                and frontier.status is StepStatus.BLOCKED
                and frontier.wait_key == wait_key
            ):
                steps[frontier.ordinal] = dataclasses.replace(
                    frontier,
                    status=StepStatus.READY,
                    due_at=now,
                    args={**frontier.args, "__payload__": payload},
                    updated_at=now,
                )
                self._append_events(
                    run_id,
                    (
                        (
                            HistoryEventType.WAIT_RESOLVED,
                            {"ordinal": frontier.ordinal, "wait_key": wait_key},
                        ),
                    ),
                    now,
                )
                return "resolved"
            self._pending.setdefault(run_id, {}).setdefault(wait_key, []).append(
                payload
            )
            self._append_events(
                run_id,
                ((HistoryEventType.SIGNAL_BUFFERED, {"wait_key": wait_key}),),
                now,
            )
            return "buffered"

    async def admit_children(
        self,
        runs: tuple[tuple[RunRecord, StepRecord], ...],
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
        now: float,
    ) -> None:
        """Create child runs, each with its root slot.

        Args:
            runs: The child run records paired with their root slots.
            events: History events to append to the parent.
            now: Current time in epoch seconds.
        """
        async with self._lock:
            for run, root_step in runs:
                self._runs[run.run_id] = run
                self._steps[run.run_id] = [root_step]
            if runs and events:
                self._append_events(runs[0][0].parent_run_id or "", events, now)

    async def record_arrival(
        self,
        run_id: str,
        ordinal: int,
        payload: dict[str, Any],
        dedupe_key: str,
        now: float,
    ) -> DeliveryDisposition:
        """Count one arrival against a join slot.

        Args:
            run_id: The waiting parent run.
            ordinal: The join slot's ordinal.
            payload: The arriving result.
            dedupe_key: Identity of the arrival.
            now: Current time in epoch seconds.

        Returns:
            What the store did with the arrival.
        """
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return "unknown_run"
            if run.status in TERMINAL_RUN_STATUSES:
                return "run_terminal"
            seen = self._inbox.setdefault(run_id, {})
            key = (run_id, f"join:{ordinal}", dedupe_key)
            if key in seen:
                return "duplicate"
            seen[key] = True
            steps = self._steps[run_id]
            step = steps[ordinal]
            if step.status is not StepStatus.BLOCKED:
                return "run_terminal"
            arrived = step.join_arrived + 1
            results = [*step.args.get("__results__", []), payload]
            done = arrived >= step.join_expected
            steps[ordinal] = dataclasses.replace(
                step,
                status=StepStatus.READY if done else StepStatus.BLOCKED,
                join_arrived=arrived,
                due_at=now if done else step.due_at,
                args={**step.args, "__results__": results},
                updated_at=now,
            )
            self._append_events(
                run_id,
                (
                    (
                        HistoryEventType.CHILD_RESOLVED,
                        {"ordinal": ordinal, "arrived": arrived},
                    ),
                ),
                now,
            )
            return "resolved" if done else "counted"

    async def count_active(self, workflow_id: str, flow_key: str) -> int:
        """Count runs of a root still in flight under a flow-control key.

        Args:
            workflow_id: The workflow identity.
            flow_key: The computed grouping key.

        Returns:
            How many non-terminal runs share the key.
        """
        async with self._lock:
            return sum(
                1
                for run in self._runs.values()
                if run.workflow_id == workflow_id
                and run.flow_key == flow_key
                and run.status not in TERMINAL_RUN_STATUSES
            )

    async def first_active(self, workflow_id: str, flow_key: str) -> RunRecord | None:
        """Find the oldest run still in flight under a flow-control key.

        Args:
            workflow_id: The workflow identity.
            flow_key: The computed grouping key.

        Returns:
            The run, or None when the key has no active run.
        """
        async with self._lock:
            active = [
                run
                for run in self._runs.values()
                if run.workflow_id == workflow_id
                and run.flow_key == flow_key
                and run.status not in TERMINAL_RUN_STATUSES
            ]
            if not active:
                return None
            return _detach_run(min(active, key=lambda run: run.created_at))

    async def count_started_since(
        self, workflow_id: str, flow_key: str, since: float
    ) -> int:
        """Count runs of a root admitted under a key since a point in time.

        Args:
            workflow_id: The workflow identity.
            flow_key: The computed grouping key.
            since: Exclusive lower bound in epoch seconds.

        Returns:
            How many runs were admitted in the window.
        """
        async with self._lock:
            return sum(
                1
                for run in self._runs.values()
                if run.workflow_id == workflow_id
                and run.flow_key == flow_key
                and run.created_at > since
            )

    async def nth_recent_start(
        self, workflow_id: str, flow_key: str, n: int
    ) -> float | None:
        """Find the nth most recent scheduled start under a flow key.

        Throttling has to place each new run relative to the ones already
        scheduled, not merely count them: deferring every excess start by one
        window replays the burst intact, one window later. Keeping each start
        at least a window after the nth most recent one spaces the backlog and
        holds the sliding-window limit.

        A run's scheduled start is when its root slot comes due, which for an
        undeferred run is when it was admitted.

        Args:
            workflow_id: The workflow identity.
            flow_key: The computed grouping key.
            n: How far back to look, counting from the most recent as 1.

        Returns:
            The scheduled start, or None when fewer than n runs exist.
        """
        async with self._lock:
            starts = sorted(
                (
                    max(steps[0].due_at, run.created_at)
                    for run in self._runs.values()
                    if run.workflow_id == workflow_id and run.flow_key == flow_key
                    if (steps := self._steps.get(run.run_id))
                ),
                reverse=True,
            )
            return starts[n - 1] if len(starts) >= n else None

    async def defer_root(self, run_id: str, due_at: float, now: float) -> bool:
        """Push a not-yet-started run's root slot later, for debouncing.

        Args:
            run_id: The pending run.
            due_at: The new earliest start time.
            now: Current time in epoch seconds.

        Returns:
            True when the root had not started and was deferred.
        """
        async with self._lock:
            steps = self._steps.get(run_id)
            if not steps or steps[0].status is not StepStatus.READY:
                return False
            steps[0] = dataclasses.replace(steps[0], due_at=due_at, updated_at=now)
            return True

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

    async def resume_run(self, run_id: str, now: float) -> bool:
        """Re-open a suspended run so its frontier step runs again.

        Args:
            run_id: The run to resume.
            now: Current time in epoch seconds.

        Returns:
            True if a suspended run was re-opened.
        """
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None or run.status is not RunStatus.NEEDS_ATTENTION:
                return False
            steps = self._steps[run_id]
            for step in list(steps):
                if step.status is StepStatus.NEEDS_ATTENTION:
                    steps[step.ordinal] = dataclasses.replace(
                        step,
                        status=StepStatus.READY,
                        attempts=0,
                        due_at=now,
                        lease_expires_at=0.0,
                        error=None,
                        updated_at=now,
                    )
            self._runs[run_id] = dataclasses.replace(
                run, status=RunStatus.PENDING, error=None, updated_at=now
            )
            self._append_events(run_id, ((HistoryEventType.RUN_RESUMED, {}),), now)
            return True

    async def recover_orphans(
        self, now: float, max_recoveries: int
    ) -> tuple[int, tuple[str, ...]]:
        """Recover claims whose lease has expired.

        Args:
            now: Current time in epoch seconds.
            max_recoveries: Recovery budget per logical step.

        Returns:
            How many steps were transitioned, and the runs failed outright.
        """
        async with self._lock:
            recovered = 0
            failed: list[str] = []
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
                        failed.append(run.run_id)
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
            return recovered, tuple(failed)

    async def list_runs(self, query: RunQuery) -> tuple[RunRecord, ...]:
        """List runs matching a query, newest first.

        Args:
            query: The filters and pagination cursor to apply.

        Returns:
            The matching run records.
        """
        async with self._lock:
            matched = [run for run in self._runs.values() if _matches_query(run, query)]
            matched.sort(key=lambda run: (run.created_at, run.run_id), reverse=True)
            return tuple(_detach_run(run) for run in matched[: query.limit])

    async def list_children(
        self, parent_run_id: str, parent_ordinal: int
    ) -> tuple[RunRecord, ...]:
        """List the child runs admitted for one join slot.

        Args:
            parent_run_id: The run that fanned out.
            parent_ordinal: The join slot the children report to.

        Returns:
            The child run records, oldest first.
        """
        async with self._lock:
            children = [
                run
                for run in self._runs.values()
                if run.parent_run_id == parent_run_id
                and run.parent_ordinal == parent_ordinal
            ]
            children.sort(key=lambda run: (run.created_at, run.run_id))
            return tuple(_detach_run(run) for run in children)

    async def find_by_request_key(
        self, workflow_id: str, request_key: str
    ) -> str | None:
        """Find the run a request key already admitted, if any.

        Args:
            workflow_id: The workflow identity.
            request_key: The idempotent admission key.

        Returns:
            The existing run id, or None when the key is unused.
        """
        async with self._lock:
            return self._dedupe.get((workflow_id, request_key))

    async def get_run(self, run_id: str) -> RunRecord | None:
        """Load one run record.

        Args:
            run_id: The run identity.

        Returns:
            The record, or None if unknown.
        """
        async with self._lock:
            run = self._runs.get(run_id)
            return None if run is None else _detach_run(run)

    async def get_steps(self, run_id: str) -> tuple[StepRecord, ...]:
        """Load a run's mailbox slots in ordinal order.

        Args:
            run_id: The run identity.

        Returns:
            The step records.
        """
        async with self._lock:
            return tuple(_detach_step(step) for step in self._steps.get(run_id, ()))

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
                wake_at = None if frontier is None else step_wake_at(frontier)
                if wake_at is not None:
                    due_times.append(wake_at)
            return min(due_times) if due_times else None


BUSY_TIMEOUT_MS: Final = 250

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
    flow_key TEXT,
    parent_run_id TEXT,
    parent_ordinal INTEGER,
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
    wait_key TEXT,
    join_expected INTEGER NOT NULL DEFAULT 0,
    join_arrived INTEGER NOT NULL DEFAULT 0,
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
CREATE TABLE IF NOT EXISTS workflow_inbox (
    run_id TEXT NOT NULL,
    wait_key TEXT NOT NULL,
    dedupe_key TEXT NOT NULL,
    seq INTEGER NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (run_id, wait_key, dedupe_key)
);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs (status);
CREATE INDEX IF NOT EXISTS idx_workflow_inbox_pending
    ON workflow_inbox (run_id, wait_key, status, seq);
"""

_STEP_MIGRATIONS: Final = (
    (
        "lease_expires_at",
        "ALTER TABLE workflow_steps ADD COLUMN lease_expires_at REAL NOT NULL DEFAULT 0",
    ),
    ("wait_key", "ALTER TABLE workflow_steps ADD COLUMN wait_key TEXT"),
    (
        "join_expected",
        "ALTER TABLE workflow_steps ADD COLUMN join_expected INTEGER NOT NULL DEFAULT 0",
    ),
    (
        "join_arrived",
        "ALTER TABLE workflow_steps ADD COLUMN join_arrived INTEGER NOT NULL DEFAULT 0",
    ),
)

_RUN_MIGRATIONS: Final = (
    ("flow_key", "ALTER TABLE workflow_runs ADD COLUMN flow_key TEXT"),
    ("parent_run_id", "ALTER TABLE workflow_runs ADD COLUMN parent_run_id TEXT"),
    ("parent_ordinal", "ALTER TABLE workflow_runs ADD COLUMN parent_ordinal INTEGER"),
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
        flow_key=row["flow_key"],
        parent_run_id=row["parent_run_id"],
        parent_ordinal=row["parent_ordinal"],
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
        wait_key=row["wait_key"],
        join_expected=row["join_expected"],
        join_arrived=row["join_arrived"],
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
        # These calls are synchronous on the caller's event loop, which also
        # serves HTTP and websockets, so a contended write must fail fast
        # rather than block everything for SQLite's multi-second default. The
        # kernel treats the resulting error as transient and retries.
        self._db.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
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
            for table, migrations in (
                ("workflow_steps", _STEP_MIGRATIONS),
                ("workflow_runs", _RUN_MIGRATIONS),
            ):
                columns = {
                    row["name"]
                    for row in self._db.execute(f"PRAGMA table_info({table})")
                }
                for name, statement in migrations:
                    if name not in columns:
                        self._db.execute(statement)
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_workflow_steps_lease"
                " ON workflow_steps (status, lease_expires_at)"
            )
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_workflow_runs_parent"
                " ON workflow_runs (parent_run_id, parent_ordinal)"
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

    def _insert_run(self, run: RunRecord) -> None:
        """Insert a run row inside the current transaction.

        Args:
            run: The run record.
        """
        self._db.execute(
            "INSERT INTO workflow_runs (run_id, workflow_id, definition_digest,"
            " status, state, state_version, next_ordinal, result, error,"
            " flow_key, parent_run_id, parent_ordinal, request_key, labels,"
            " deadline, cancel_requested, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                run.flow_key,
                run.parent_run_id,
                run.parent_ordinal,
                run.request_key,
                _dump(run.labels),
                run.deadline,
                int(run.cancel_requested),
                run.created_at,
                run.updated_at,
            ),
        )

    def _insert_step(self, step: StepRecord) -> None:
        """Insert a step row inside the current transaction.

        Args:
            step: The step record.
        """
        self._db.execute(
            "INSERT INTO workflow_steps (run_id, ordinal, handler_id, status, args,"
            " attempts, recoveries, due_at, epoch, lease_expires_at, wait_key,"
            " join_expected, join_arrived, error, origin, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                step.wait_key,
                step.join_expected,
                step.join_arrived,
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
                self._insert_run(run)
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
                    if frontier is None or not step_claimable_at(frontier, now):
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

    def _arm_sql(self, step: StepRecord, now: float) -> StepRecord:
        """Resolve a newly armed wait against a buffered delivery, in-transaction.

        Args:
            step: The slot being inserted.
            now: Current time in epoch seconds.

        Returns:
            The slot, already resolved when a matching delivery was waiting.
        """
        if step.status is not StepStatus.BLOCKED or step.wait_key is None:
            return step
        row = self._db.execute(
            "SELECT dedupe_key, payload FROM workflow_inbox"
            " WHERE run_id = ? AND wait_key = ? AND status = ?"
            " ORDER BY seq LIMIT 1",
            (step.run_id, step.wait_key, "PENDING"),
        ).fetchone()
        if row is None:
            return step
        self._db.execute(
            "UPDATE workflow_inbox SET status = ?"
            " WHERE run_id = ? AND wait_key = ? AND dedupe_key = ?",
            ("CONSUMED", step.run_id, step.wait_key, row["dedupe_key"]),
        )
        return dataclasses.replace(
            step,
            status=StepStatus.READY,
            due_at=now,
            args={**step.args, "__payload__": json.loads(row["payload"])},
            updated_at=now,
        )

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
                    self._insert_step(self._arm_sql(step, now))
                for child_run, child_step in completion.children:
                    self._insert_run(child_run)
                    self._insert_step(child_step)
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

    async def deliver(
        self,
        run_id: str,
        wait_key: str,
        dedupe_key: str,
        payload: dict[str, Any],
        now: float,
    ) -> DeliveryDisposition:
        """Deliver a payload to a run, resolving its wait or buffering it.

        Args:
            run_id: The receiving run.
            wait_key: The address the waiting slot declared.
            dedupe_key: Sender-supplied identity, making redelivery a no-op.
            payload: JSON-compatible payload to hand the resuming handler.
            now: Current time in epoch seconds.

        Returns:
            What the store did with the delivery.
        """
        terminal = tuple(s.value for s in TERMINAL_RUN_STATUSES)
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row = self._db.execute(
                    "SELECT status FROM workflow_runs WHERE run_id = ?", (run_id,)
                ).fetchone()
                if row is None:
                    self._db.execute("ROLLBACK")
                    return "unknown_run"
                if row["status"] in terminal:
                    self._db.execute("ROLLBACK")
                    return "run_terminal"
                seen = self._db.execute(
                    "SELECT 1 FROM workflow_inbox"
                    " WHERE run_id = ? AND wait_key = ? AND dedupe_key = ?",
                    (run_id, wait_key, dedupe_key),
                ).fetchone()
                if seen is not None:
                    self._db.execute("ROLLBACK")
                    return "duplicate"
                frontier = _frontier(self._load_steps(run_id))
                if frontier is not None and _wait_expired(frontier, now):
                    self._db.execute("ROLLBACK")
                    return "expired"
                resolves = (
                    frontier is not None
                    and frontier.status is StepStatus.BLOCKED
                    and frontier.wait_key == wait_key
                )
                self._db.execute(
                    "INSERT INTO workflow_inbox (run_id, wait_key, dedupe_key, seq,"
                    " payload, status, created_at)"
                    " VALUES (?, ?, ?, (SELECT COALESCE(MAX(seq), 0) + 1 FROM"
                    " workflow_inbox WHERE run_id = ?), ?, ?, ?)",
                    (
                        run_id,
                        wait_key,
                        dedupe_key,
                        run_id,
                        json.dumps(payload),
                        "CONSUMED" if resolves else "PENDING",
                        now,
                    ),
                )
                if resolves and frontier is not None:
                    self._db.execute(
                        "UPDATE workflow_steps SET status = ?, due_at = ?, args = ?,"
                        " updated_at = ? WHERE run_id = ? AND ordinal = ?",
                        (
                            StepStatus.READY.value,
                            now,
                            json.dumps({**frontier.args, "__payload__": payload}),
                            now,
                            run_id,
                            frontier.ordinal,
                        ),
                    )
                    self._append_events(
                        run_id,
                        (
                            (
                                HistoryEventType.WAIT_RESOLVED,
                                {"ordinal": frontier.ordinal, "wait_key": wait_key},
                            ),
                        ),
                        now,
                    )
                else:
                    self._append_events(
                        run_id,
                        ((HistoryEventType.SIGNAL_BUFFERED, {"wait_key": wait_key}),),
                        now,
                    )
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            return "resolved" if resolves else "buffered"

    async def admit_children(
        self,
        runs: tuple[tuple[RunRecord, StepRecord], ...],
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
        now: float,
    ) -> None:
        """Create child runs, each with its root slot.

        Args:
            runs: The child run records paired with their root slots.
            events: History events to append to the parent.
            now: Current time in epoch seconds.
        """
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                for run, root_step in runs:
                    self._insert_run(run)
                    self._insert_step(root_step)
                if runs and events:
                    self._append_events(runs[0][0].parent_run_id or "", events, now)
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    async def record_arrival(
        self,
        run_id: str,
        ordinal: int,
        payload: dict[str, Any],
        dedupe_key: str,
        now: float,
    ) -> DeliveryDisposition:
        """Count one arrival against a join slot.

        Args:
            run_id: The waiting parent run.
            ordinal: The join slot's ordinal.
            payload: The arriving result.
            dedupe_key: Identity of the arrival.
            now: Current time in epoch seconds.

        Returns:
            What the store did with the arrival.
        """
        terminal = tuple(s.value for s in TERMINAL_RUN_STATUSES)
        wait_key = f"join:{ordinal}"
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                run_row = self._db.execute(
                    "SELECT status FROM workflow_runs WHERE run_id = ?", (run_id,)
                ).fetchone()
                if run_row is None:
                    self._db.execute("ROLLBACK")
                    return "unknown_run"
                if run_row["status"] in terminal:
                    self._db.execute("ROLLBACK")
                    return "run_terminal"
                seen = self._db.execute(
                    "SELECT 1 FROM workflow_inbox"
                    " WHERE run_id = ? AND wait_key = ? AND dedupe_key = ?",
                    (run_id, wait_key, dedupe_key),
                ).fetchone()
                if seen is not None:
                    self._db.execute("ROLLBACK")
                    return "duplicate"
                step_row = self._db.execute(
                    "SELECT * FROM workflow_steps WHERE run_id = ? AND ordinal = ?",
                    (run_id, ordinal),
                ).fetchone()
                if step_row is None or step_row["status"] != StepStatus.BLOCKED.value:
                    self._db.execute("ROLLBACK")
                    return "run_terminal"
                step = _step_from_row(step_row)
                self._db.execute(
                    "INSERT INTO workflow_inbox (run_id, wait_key, dedupe_key, seq,"
                    " payload, status, created_at)"
                    " VALUES (?, ?, ?, (SELECT COALESCE(MAX(seq), 0) + 1 FROM"
                    " workflow_inbox WHERE run_id = ?), ?, ?, ?)",
                    (
                        run_id,
                        wait_key,
                        dedupe_key,
                        run_id,
                        json.dumps(payload),
                        "CONSUMED",
                        now,
                    ),
                )
                arrived = step.join_arrived + 1
                results = [*step.args.get("__results__", []), payload]
                done = arrived >= step.join_expected
                self._db.execute(
                    "UPDATE workflow_steps SET status = ?, join_arrived = ?,"
                    " due_at = ?, args = ?, updated_at = ?"
                    " WHERE run_id = ? AND ordinal = ? AND join_arrived = ?",
                    (
                        StepStatus.READY.value if done else StepStatus.BLOCKED.value,
                        arrived,
                        now if done else step.due_at,
                        json.dumps({**step.args, "__results__": results}),
                        now,
                        run_id,
                        ordinal,
                        step.join_arrived,
                    ),
                )
                self._append_events(
                    run_id,
                    (
                        (
                            HistoryEventType.CHILD_RESOLVED,
                            {"ordinal": ordinal, "arrived": arrived},
                        ),
                    ),
                    now,
                )
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            return "resolved" if done else "counted"

    async def count_active(self, workflow_id: str, flow_key: str) -> int:
        """Count runs of a root still in flight under a flow-control key.

        Args:
            workflow_id: The workflow identity.
            flow_key: The computed grouping key.

        Returns:
            How many non-terminal runs share the key.
        """
        terminal = tuple(s.value for s in TERMINAL_RUN_STATUSES)
        with self._lock:
            row = self._db.execute(
                "SELECT COUNT(*) AS n FROM workflow_runs"
                " WHERE workflow_id = ? AND flow_key = ?"
                f" AND status NOT IN ({','.join('?' * len(terminal))})",
                (workflow_id, flow_key, *terminal),
            ).fetchone()
            return row["n"]

    async def first_active(self, workflow_id: str, flow_key: str) -> RunRecord | None:
        """Find the oldest run still in flight under a flow-control key.

        Args:
            workflow_id: The workflow identity.
            flow_key: The computed grouping key.

        Returns:
            The run, or None when the key has no active run.
        """
        terminal = tuple(s.value for s in TERMINAL_RUN_STATUSES)
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM workflow_runs"
                " WHERE workflow_id = ? AND flow_key = ?"
                f" AND status NOT IN ({','.join('?' * len(terminal))})"
                " ORDER BY created_at LIMIT 1",
                (workflow_id, flow_key, *terminal),
            ).fetchone()
            return None if row is None else _run_from_row(row)

    async def count_started_since(
        self, workflow_id: str, flow_key: str, since: float
    ) -> int:
        """Count runs of a root admitted under a key since a point in time.

        Args:
            workflow_id: The workflow identity.
            flow_key: The computed grouping key.
            since: Exclusive lower bound in epoch seconds.

        Returns:
            How many runs were admitted in the window.
        """
        with self._lock:
            row = self._db.execute(
                "SELECT COUNT(*) AS n FROM workflow_runs"
                " WHERE workflow_id = ? AND flow_key = ? AND created_at > ?",
                (workflow_id, flow_key, since),
            ).fetchone()
            return row["n"]

    async def nth_recent_start(
        self, workflow_id: str, flow_key: str, n: int
    ) -> float | None:
        """Find the nth most recent scheduled start under a flow key.

        Throttling has to place each new run relative to the ones already
        scheduled, not merely count them: deferring every excess start by one
        window replays the burst intact, one window later. Keeping each start
        at least a window after the nth most recent one spaces the backlog and
        holds the sliding-window limit.

        A run's scheduled start is when its root slot comes due, which for an
        undeferred run is when it was admitted.

        Args:
            workflow_id: The workflow identity.
            flow_key: The computed grouping key.
            n: How far back to look, counting from the most recent as 1.

        Returns:
            The scheduled start, or None when fewer than n runs exist.
        """
        with self._lock:
            row = self._db.execute(
                "SELECT MAX(s.due_at, r.created_at) AS start FROM workflow_runs r"
                " JOIN workflow_steps s ON s.run_id = r.run_id AND s.ordinal = 0"
                " WHERE r.workflow_id = ? AND r.flow_key = ?"
                " ORDER BY start DESC LIMIT 1 OFFSET ?",
                (workflow_id, flow_key, n - 1),
            ).fetchone()
            return None if row is None else row["start"]

    async def defer_root(self, run_id: str, due_at: float, now: float) -> bool:
        """Push a not-yet-started run's root slot later, for debouncing.

        Args:
            run_id: The pending run.
            due_at: The new earliest start time.
            now: Current time in epoch seconds.

        Returns:
            True when the root had not started and was deferred.
        """
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                cursor = self._db.execute(
                    "UPDATE workflow_steps SET due_at = ?, updated_at = ?"
                    " WHERE run_id = ? AND ordinal = 0 AND status = ?",
                    (due_at, now, run_id, StepStatus.READY.value),
                )
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            return cursor.rowcount > 0

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

    async def resume_run(self, run_id: str, now: float) -> bool:
        """Re-open a suspended run so its frontier step runs again.

        Args:
            run_id: The run to resume.
            now: Current time in epoch seconds.

        Returns:
            True if a suspended run was re-opened.
        """
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                cursor = self._db.execute(
                    "UPDATE workflow_runs SET status = ?, error = NULL,"
                    " updated_at = ? WHERE run_id = ? AND status = ?",
                    (
                        RunStatus.PENDING.value,
                        now,
                        run_id,
                        RunStatus.NEEDS_ATTENTION.value,
                    ),
                )
                if cursor.rowcount == 0:
                    self._db.execute("ROLLBACK")
                    return False
                self._db.execute(
                    "UPDATE workflow_steps SET status = ?, attempts = 0, due_at = ?,"
                    " lease_expires_at = 0, error = NULL, updated_at = ?"
                    " WHERE run_id = ? AND status = ?",
                    (
                        StepStatus.READY.value,
                        now,
                        now,
                        run_id,
                        StepStatus.NEEDS_ATTENTION.value,
                    ),
                )
                self._append_events(run_id, ((HistoryEventType.RUN_RESUMED, {}),), now)
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            return True

    async def recover_orphans(
        self, now: float, max_recoveries: int
    ) -> tuple[int, tuple[str, ...]]:
        """Recover claims whose lease has expired.

        Args:
            now: Current time in epoch seconds.
            max_recoveries: Recovery budget per logical step.

        Returns:
            How many steps were transitioned, and the runs failed outright.
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
                failed: list[str] = []
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
                        failed.append(step.run_id)
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
            return recovered, tuple(failed)

    async def list_runs(self, query: RunQuery) -> tuple[RunRecord, ...]:
        """List runs matching a query, newest first.

        Args:
            query: The filters and pagination cursor to apply.

        Returns:
            The matching run records.
        """
        clauses: list[str] = []
        params: list[Any] = []
        if query.workflow_id is not None:
            clauses.append("workflow_id = ?")
            params.append(query.workflow_id)
        if query.statuses:
            placeholders = ",".join("?" * len(query.statuses))
            clauses.append(f"status IN ({placeholders})")
            params.extend(status.value for status in query.statuses)
        if query.created_before is not None:
            clauses.append("(created_at, run_id) < (?, ?)")
            params.extend(query.created_before)
        for key, value in (query.labels or {}).items():
            # The key comes from user data, so it is matched as a value rather
            # than spliced into a JSON path expression.
            clauses.append(
                "EXISTS (SELECT 1 FROM json_each(labels)"
                " WHERE json_each.key = ? AND json_each.value = ?)"
            )
            params.extend((key, value))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            rows = self._db.execute(
                f"SELECT * FROM workflow_runs{where}"
                " ORDER BY created_at DESC, run_id DESC LIMIT ?",
                (*params, query.limit),
            ).fetchall()
            return tuple(_run_from_row(row) for row in rows)

    async def list_children(
        self, parent_run_id: str, parent_ordinal: int
    ) -> tuple[RunRecord, ...]:
        """List the child runs admitted for one join slot.

        Args:
            parent_run_id: The run that fanned out.
            parent_ordinal: The join slot the children report to.

        Returns:
            The child run records, oldest first.
        """
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM workflow_runs WHERE parent_run_id = ?"
                " AND parent_ordinal = ? ORDER BY created_at, run_id",
                (parent_run_id, parent_ordinal),
            ).fetchall()
            return tuple(_run_from_row(row) for row in rows)

    async def find_by_request_key(
        self, workflow_id: str, request_key: str
    ) -> str | None:
        """Find the run a request key already admitted, if any.

        Args:
            workflow_id: The workflow identity.
            request_key: The idempotent admission key.

        Returns:
            The existing run id, or None when the key is unused.
        """
        with self._lock:
            row = self._db.execute(
                "SELECT run_id FROM workflow_dedupe"
                " WHERE workflow_id = ? AND request_key = ?",
                (workflow_id, request_key),
            ).fetchone()
            return None if row is None else row["run_id"]

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
                wake_at = None if frontier is None else step_wake_at(frontier)
                if wake_at is not None:
                    due_times.append(wake_at)
            return min(due_times) if due_times else None
