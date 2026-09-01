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
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, Protocol

from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import DEFAULT_LEASE_DURATION

from reflex.workflow.records import (
    CLAIMABLE_STEP_STATUSES,
    TERMINAL_RUN_STATUSES,
    TERMINAL_STEP_STATUSES,
    AuditEntry,
    HistoryEvent,
    HistoryEventType,
    ParkedDelivery,
    ParkedStatus,
    RunQuery,
    RunRecord,
    RunStatus,
    StepRecord,
    StepStatus,
    WorkerRecord,
    step_claimable_at,
    step_wake_at,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


DeliveryDisposition = Literal[
    "resolved",
    "counted",
    "expired",
    "buffered",
    "duplicate",
    "unknown_run",
    "run_terminal",
    "unknown_key",
    "parked",
    "dead_letter",
]


class DeadlinePassedError(WorkflowRuntimeError):
    """A commit arrived after its run's deadline.

    The contract promises a run past its deadline finalizes TIMED_OUT, which
    is only unambiguous if nothing can commit afterwards: an attempt that
    beats the timeout sweep would otherwise record COMPLETED on a run the
    caller was told had timed out. The attempt's recorded substeps stand --
    this is crash-equivalent, not an undo.
    """


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
        parent_arrival: When this transition ends a child run, the arrival to
            deliver to its parent's join slot, as (parent_run_id, ordinal,
            payload, dedupe_key). Delivered inside this transaction: a crash
            between a child finishing and its parent hearing about it would
            leave the join waiting forever.
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
    parent_arrival: tuple[str, int, dict[str, Any], str] | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class FlowGate:
    """One root's start policy, evaluated inside the admitting transaction.

    A start policy is a read followed by a write -- count the active runs,
    then insert or refuse -- and any gap between the two is a race that
    concurrent starts in different processes both win. The kernel used to
    guard the gap with an asyncio lock, which serializes one process and
    nothing else. The whole decision therefore belongs to the store, executed
    under a durable per-key lock, and this value is the policy handed in.

    Attributes:
        singleton_skip: Refuse the start while any run is active on the key.
        singleton_cancel: Request cancellation of every active run on the key
            before admitting the replacement, in the same transaction.
        rate_limit: ``(limit, window_seconds)``; refuse once the key has had
            that many starts inside the window.
        throttle: ``(limit, window_seconds)``; delay the root so each start
            sits a window after the limit-th most recent one.
        debounce: Quiet-period seconds; an existing pending root absorbs this
            start, taking its payload and a fresh deadline.
    """

    singleton_skip: bool = False
    singleton_cancel: bool = False
    rate_limit: tuple[int, float] | None = None
    throttle: tuple[int, float] | None = None
    debounce: float | None = None

    def __post_init__(self):
        """Refuse combined policies.

        The decorator already enforces one policy per root; this makes the
        combinations unrepresentable at the store boundary too, because the
        three stores genuinely diverge on what a half-applied combination
        would leave behind (a rejected start after a singleton cancellation
        rolls back on SQLite and commits elsewhere), and an invariant that
        holds only because callers are polite is not an invariant.

        Raises:
            ValueError: If more than one policy is declared.
        """
        declared = sum(
            1
            for flag in (
                self.singleton_skip,
                self.singleton_cancel,
                self.rate_limit is not None,
                self.throttle is not None,
                self.debounce is not None,
            )
            if flag
        )
        if declared > 1:
            msg = "FlowGate takes exactly one policy; combinations diverge."
            raise ValueError(msg)


@dataclasses.dataclass(frozen=True, slots=True)
class FlowAdmission:
    """What one gated admission did, decided atomically by the store.

    Attributes:
        disposition: How the submission was handled.
        run_id: The created or prior run, when one identifies the outcome.
        retry_after: Suggested resubmission delay for a rejected start.
        cancelled: Runs whose cancellation this admission requested, for the
            kernel to stop locally and finalize.
    """

    disposition: Literal["started", "skipped", "rejected", "coalesced", "deduplicated"]
    run_id: str | None = None
    retry_after: float | None = None
    cancelled: tuple[str, ...] = ()


class RunStore(Protocol):
    """Protocol implemented by workflow run stores."""

    async def admit(
        self,
        run: RunRecord,
        root_step: StepRecord,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
    ) -> tuple[bool, str]:
        """Atomically admit a run, deduplicating on the request key.

        Roots with a start policy are admitted through ``admit_flow``, where
        the whole policy decision shares the admitting transaction.

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
        self,
        now: float,
        *,
        lease_duration: float = DEFAULT_LEASE_DURATION,
        queues: tuple[str, ...] | None = None,
        release: str | None = None,
    ) -> Claim | None:
        """Claim the due frontier step of some runnable run.

        The claim carries a lease expiring at ``now + lease_duration``. The
        executing kernel must renew it through ``renew_lease``; a claim whose
        lease lapses is reclaimed by ``recover_orphans``.

        Args:
            now: Current time in epoch seconds.
            lease_duration: Seconds of renewal silence tolerated before the
                claim is treated as orphaned.
            queues: Queues this worker serves; None serves every queue. A run
                whose frontier sits on an unserved queue is skipped whole,
                because claiming a later slot would break its ordering.
            release: The claiming worker's release identity. A run pinned
                to a different release is skipped: it drains on the release
                that admitted it, so one run never mixes two releases' code.

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
        payload: Any,
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

    async def register_worker(self, worker: WorkerRecord) -> None:
        """Record (or refresh) a worker's registration.

        Args:
            worker: The worker's identity, release, queues, and capacity.
        """
        ...

    async def heartbeat_worker(self, worker_id: str, now: float) -> None:
        """Refresh a worker's sign of life.

        Args:
            worker_id: The worker.
            now: Current time in epoch seconds.
        """
        ...

    async def deregister_worker(self, worker_id: str) -> None:
        """Remove a worker that shut down cleanly.

        Args:
            worker_id: The worker.
        """
        ...

    async def list_workers(self) -> tuple[WorkerRecord, ...]:
        """List registered workers, most recently started first.

        A worker that died without deregistering stays listed with a stale
        heartbeat; staleness is the reader's judgement, because only the
        reader knows what cadence it expects.

        Returns:
            The registrations.
        """
        ...

    async def ingest_channel_delivery(
        self,
        workflow_id: str,
        channel: str,
        correlation_key: str,
        dedupe_key: str,
        payload: Any,
        now: float,
    ) -> DeliveryDisposition:
        """Durably accept a correlated provider event, exactly once.

        The row keyed by the provider's event id is written first, in the
        same transaction as any delivery, so acknowledging the provider and
        recording the event are one fact: a crash after the ack replays as
        ``duplicate``, never as a second signal. If the correlation key
        already admitted a run, the payload is delivered to it here; if not,
        the row waits PENDING for the run to be admitted; if the run is
        terminal or past its deadline, the row becomes a DEAD letter an
        operator can see and replay.

        Args:
            workflow_id: The workflow whose channel the event addresses.
            channel: The channel name.
            correlation_key: The business key naming the target run.
            dedupe_key: The provider's event identity.
            payload: The canonical event payload.
            now: Current time in epoch seconds.

        Returns:
            ``resolved``/``buffered`` when delivered, ``duplicate`` for a
            redelivery, ``parked`` when no run exists yet, ``dead_letter``
            when the run can no longer take it.
        """
        ...

    async def list_parked(
        self,
        *,
        workflow_id: str | None = None,
        status: ParkedStatus | None = None,
        limit: int = 100,
    ) -> tuple[ParkedDelivery, ...]:
        """List channel-inbox deliveries, newest first.

        Args:
            workflow_id: Restrict to one workflow.
            status: Restrict to one lifecycle state.
            limit: Maximum rows.

        Returns:
            The matching deliveries.
        """
        ...

    async def replay_parked(
        self,
        parked_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> DeliveryDisposition:
        """Re-attempt routing of a parked or dead delivery.

        The operator's answer to a dead letter whose cause is fixed: the row
        goes through the same routing as ingest, with the same idempotency,
        so replaying a delivery that already reached its run is a
        ``duplicate``, never a second signal. With attribution, the replay is
        written to the audit log in the same transaction.

        Args:
            parked_id: The delivery to replay.
            now: Current time in epoch seconds.
            attribution: Who asked and why, recorded in the audit log.

        Returns:
            The routing outcome, or ``unknown_key`` if no such delivery.
        """
        ...

    async def list_audit(
        self, *, action: str | None = None, limit: int = 100
    ) -> tuple[AuditEntry, ...]:
        """List audited operator actions, newest first.

        Args:
            action: Restrict to one action name.
            limit: Maximum entries.

        Returns:
            The matching entries.
        """
        ...

    async def set_schedule_paused(
        self,
        key: str,
        paused: bool,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> None:
        """Pause or resume a schedule, durably.

        A paused schedule's occurrences are skipped -- its cursor still
        advances, so resuming never backfills the pause -- and the decision
        is written to the audit log in the same transaction when attributed.

        Args:
            key: The schedule identity, "{workflow_id}:{handler_id}".
            paused: Whether the schedule should skip its occurrences.
            now: Current time in epoch seconds.
            attribution: Who asked and why, recorded in the audit log.
        """
        ...

    async def paused_schedules(self) -> frozenset[str]:
        """The schedules currently paused.

        Returns:
            Their keys.
        """
        ...

    async def sweep_parked(self, now: float, ttl: float) -> int:
        """Turn PENDING deliveries older than a ttl into DEAD letters.

        A delivery whose run never arrived must eventually become visible as
        a problem rather than waiting forever: ``unclaimed`` dead letters are
        what an operator alerts on.

        Args:
            now: Current time in epoch seconds.
            ttl: Age in seconds beyond which PENDING is unclaimed.

        Returns:
            How many deliveries became dead letters.
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

    async def admit_flow(
        self,
        run: RunRecord,
        root_step: StepRecord,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
        gate: FlowGate,
        now: float,
    ) -> FlowAdmission:
        """Admit a run under a start policy, atomically.

        The dedupe check, every policy read, any policy mutation, and the
        insert happen in one transaction under a durable lock on the run's
        ``(workflow_id, flow_key)``, so two processes admitting concurrently
        cannot both pass a limit of one. Policies apply in declaration order:
        dedupe, singleton, rate limit, throttle, debounce.

        Args:
            run: The run record to create, carrying the flow key.
            root_step: The preallocated root mailbox slot.
            events: History events to append on creation.
            gate: The policy to enforce.
            now: Current time in epoch seconds.

        Returns:
            What was done, decided inside the transaction.
        """
        ...

    async def epoch_time(self) -> float | None:
        """The store's own current time, when it has one all workers share.

        Worker wall clocks skew, and every scheduling comparison -- lease
        expiry, due times, schedule occurrence keys -- is only safe when the
        comparands come from one clock. A store shared by many machines
        (Postgres) answers with its database clock so every worker can derive
        time from the same authority; a store that never leaves one host
        answers None, because the host clock already is that authority.

        Returns:
            Epoch seconds by the store's clock, or None when the process
            clock is the right authority.
        """
        ...

    async def purge_runs(
        self,
        before: float,
        *,
        workflow_id: str | None = None,
        attribution: Mapping[str, str] | None = None,
    ) -> int:
        """Delete terminal runs not updated since a cutoff, and all their data.

        Terminal data otherwise grows forever. Purging a run also forgets its
        request key, so a provider redelivery arriving after the retention
        window is admitted as a new run: retention must exceed the provider's
        redelivery horizon.

        Args:
            before: Delete runs whose last update is older than this.
            workflow_id: Restrict to one workflow identity.
            attribution: Who asked and why, recorded in the audit log.

        Returns:
            How many runs were deleted.
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

    async def request_cancel(
        self,
        run_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Record cancellation intent on a run.

        Args:
            run_id: The run to cancel.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".

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
        result: Any = None,
        parent_arrival: tuple[str, int, dict[str, Any], str] | None = None,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Terminate a drained run and tombstone its unresolved slots.

        Args:
            run_id: The run to finalize.
            status: The terminal status to record.
            error: Error payload recorded on the run.
            event: The terminal history event type.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".
            result: Result to record, for an operator forcing completion.
            parent_arrival: When this run is a child, the arrival to deliver
                to its parent's join, applied in this same transaction.

        Returns:
            True if the run was finalized; False if it was already terminal
            or still has a claimed step.
        """
        ...

    async def skip_step(
        self,
        run_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Give up on a stuck step and let the run carry on past it.

        The operator's answer to a step that cannot succeed and is not worth
        failing the run over -- a vendor that retired an endpoint, a
        notification nobody needs any more. The step is marked SKIPPED, which
        is terminal and recorded as a decision rather than an outcome, and the
        run continues at whatever comes next. Legal only on a run stopped for
        attention or failure, so it can never race a working attempt.

        Args:
            run_id: The run to unstick.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".

        Returns:
            True if a blocking step was skipped.
        """
        ...

    async def retry_run(
        self,
        run_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Re-open a failed run at the step that failed.

        The operator's answer to a run that failed for a reason now fixed: the
        failed step runs again with a fresh attempt budget, and the failure
        stays in history rather than being erased.

        Args:
            run_id: The run to retry.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".

        Returns:
            True if a failed run was re-opened.
        """
        ...

    async def resume_run(
        self,
        run_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Re-open a suspended run so its frontier step runs again.

        Suspension is an operator state, not an outcome: the run waits for a
        human to fix whatever made the outcome uncertain. Resuming clears the
        error, grants the frontier step a fresh attempt budget, and makes it
        claimable immediately.

        Args:
            run_id: The run to resume.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".

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

    async def count_runs(self, query: RunQuery) -> int:
        """Count runs matching a query.

        The count ignores ``limit`` and ``created_before``: those page a
        listing, and an aggregate is not a page. Everything else filters as
        it does for ``list_runs``, so a count and a listing always describe
        the same set.

        Args:
            query: The filters to apply.

        Returns:
            How many runs match.
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

    async def record_substep(
        self, run_id: str, ordinal: int, epoch: int, key: str, payload: Any, now: float
    ) -> bool:
        """Durably record one substep result inside a claimed attempt.

        The write is fenced on the step's claim epoch: an attempt whose lease
        was reclaimed must not pollute the journal a newer attempt is reading.
        The first write for a key wins, so a duplicate is a no-op that still
        reports success -- memoization reads before it writes, so a duplicate
        only means two racing writers agreed.

        Args:
            run_id: The owning run.
            ordinal: The mailbox slot being executed.
            epoch: The claim fence of the writing attempt.
            key: The substep's memoization key, unique within the step.
            payload: JSON-compatible result to record.
            now: Current time in epoch seconds.

        Returns:
            True when recorded (or already recorded); False when the writer
            was fenced and must stop.
        """
        ...

    async def get_substeps(self, run_id: str, ordinal: int) -> dict[str, Any]:
        """Load the recorded substep results of one step.

        Args:
            run_id: The owning run.
            ordinal: The mailbox slot.

        Returns:
            Recorded payloads by key, in recording order.
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

    async def read_schedule_cursor(self, key: str) -> float | None:
        """Read where a schedule's catch-up last reached.

        Args:
            key: The schedule identity, "{workflow_id}:{handler_id}".

        Returns:
            The last swept time, or None when the schedule is new here.
        """
        ...

    async def write_schedule_cursor(self, key: str, at: float) -> None:
        """Record where a schedule's catch-up has now reached.

        Persisting this is what makes a restart resume rather than silently
        skip: an in-memory cursor reseeded at startup treats every occurrence
        during the downtime as if it had already fired.

        Args:
            key: The schedule identity, "{workflow_id}:{handler_id}".
            at: The time swept up to, in epoch seconds.
        """
        ...

    async def next_due(
        self, now: float, *, queues: tuple[str, ...] | None = None
    ) -> float | None:
        """Earliest future time any runnable run becomes claimable.

        Args:
            now: Current time in epoch seconds.
            queues: Queues this worker serves; None serves every queue.

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
    if (
        query.definition_digest is not None
        and run.definition_digest != query.definition_digest
    ):
        return False
    if query.release_id is not None and run.release_id != query.release_id:
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
        self._substeps: dict[tuple[str, int], dict[str, Any]] = {}
        self._schedule_cursors: dict[str, float] = {}
        self._parked: list[ParkedDelivery] = []
        self._audit: list[AuditEntry] = []
        self._paused_schedules: set[str] = set()
        self._workers: dict[str, WorkerRecord] = {}
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

        Roots with a start policy are admitted through ``admit_flow``, where
        the whole policy decision shares the admitting transaction.

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
            if run.request_key is not None:
                self._dedupe[run.workflow_id, run.request_key] = run.run_id
            self._runs[run.run_id] = run
            self._steps[run.run_id] = [root_step]
            self._append_events(run.run_id, events, run.created_at)
            if run.request_key is not None:
                # Deliveries that arrived before this run did: flushed inside
                # the admitting transaction, so a crash cannot separate "the
                # run exists" from "its early mail reached it".
                self._flush_parked_locked(
                    run.workflow_id, run.request_key, run.run_id, run.created_at
                )
            return True, run.run_id

    def _flush_parked_locked(
        self, workflow_id: str, request_key: str, run_id: str, now: float
    ) -> None:
        """Deliver PENDING channel-inbox rows to a freshly admitted run.

        Args:
            workflow_id: The workflow identity.
            request_key: The admission key, matched against correlation keys.
            run_id: The run that now exists.
            now: Current time in epoch seconds.
        """
        for index, parked in enumerate(self._parked):
            if (
                parked.status is not ParkedStatus.PENDING
                or parked.workflow_id != workflow_id
                or parked.correlation_key != request_key
            ):
                continue
            disposition = self._deliver_locked(
                run_id,
                f"sig:{parked.channel}",
                parked.dedupe_key,
                parked.payload,
                now,
            )
            if disposition in ("resolved", "buffered", "duplicate"):
                self._parked[index] = dataclasses.replace(
                    parked,
                    status=ParkedStatus.DELIVERED,
                    run_id=run_id,
                    updated_at=now,
                )
            else:
                self._parked[index] = dataclasses.replace(
                    parked,
                    status=ParkedStatus.DEAD,
                    reason=disposition,
                    updated_at=now,
                )

    async def register_worker(self, worker: WorkerRecord) -> None:
        """Record (or refresh) a worker's registration.

        Args:
            worker: The worker's identity, release, queues, and capacity.
        """
        async with self._lock:
            self._workers[worker.worker_id] = worker

    async def heartbeat_worker(self, worker_id: str, now: float) -> None:
        """Refresh a worker's sign of life.

        Args:
            worker_id: The worker.
            now: Current time in epoch seconds.
        """
        async with self._lock:
            worker = self._workers.get(worker_id)
            if worker is not None:
                self._workers[worker_id] = dataclasses.replace(worker, heartbeat_at=now)

    async def deregister_worker(self, worker_id: str) -> None:
        """Remove a worker that shut down cleanly.

        Args:
            worker_id: The worker.
        """
        async with self._lock:
            self._workers.pop(worker_id, None)

    async def list_workers(self) -> tuple[WorkerRecord, ...]:
        """List registered workers, most recently started first.

        Returns:
            The registrations.
        """
        async with self._lock:
            return tuple(
                sorted(
                    self._workers.values(),
                    key=lambda worker: worker.started_at,
                    reverse=True,
                )
            )

    async def ingest_channel_delivery(
        self,
        workflow_id: str,
        channel: str,
        correlation_key: str,
        dedupe_key: str,
        payload: Any,
        now: float,
    ) -> DeliveryDisposition:
        """Durably accept a correlated provider event, exactly once.

        Args:
            workflow_id: The workflow whose channel the event addresses.
            channel: The channel name.
            correlation_key: The business key naming the target run.
            dedupe_key: The provider's event identity.
            payload: The canonical event payload.
            now: Current time in epoch seconds.

        Returns:
            The routing outcome.
        """
        async with self._lock:
            for parked in self._parked:
                if (
                    parked.workflow_id == workflow_id
                    and parked.channel == channel
                    and parked.correlation_key == correlation_key
                    and parked.dedupe_key == dedupe_key
                ):
                    # The event id is the identity: a provider redelivery and
                    # a crash-after-ack replay both land here, whatever state
                    # the earlier row reached.
                    return "duplicate"
            record = ParkedDelivery(
                parked_id=uuid.uuid4().hex,
                workflow_id=workflow_id,
                channel=channel,
                correlation_key=correlation_key,
                dedupe_key=dedupe_key,
                payload=payload,
                status=ParkedStatus.PENDING,
                reason=None,
                run_id=None,
                created_at=now,
                updated_at=now,
            )
            self._parked.append(record)
            return self._route_parked_locked(len(self._parked) - 1, now)

    def _route_parked_locked(self, index: int, now: float) -> DeliveryDisposition:
        """Route one PENDING channel-inbox row to its run, if it exists yet.

        Args:
            index: The row's position.
            now: Current time in epoch seconds.

        Returns:
            The routing outcome.
        """
        parked = self._parked[index]
        run_id = self._dedupe.get((parked.workflow_id, parked.correlation_key))
        if run_id is None:
            return "parked"
        disposition = self._deliver_locked(
            run_id, f"sig:{parked.channel}", parked.dedupe_key, parked.payload, now
        )
        if disposition in ("resolved", "buffered", "duplicate"):
            self._parked[index] = dataclasses.replace(
                parked,
                status=ParkedStatus.DELIVERED,
                run_id=run_id,
                updated_at=now,
            )
            return disposition if disposition != "duplicate" else "duplicate"
        self._parked[index] = dataclasses.replace(
            parked, status=ParkedStatus.DEAD, reason=disposition, updated_at=now
        )
        return "dead_letter"

    async def list_parked(
        self,
        *,
        workflow_id: str | None = None,
        status: ParkedStatus | None = None,
        limit: int = 100,
    ) -> tuple[ParkedDelivery, ...]:
        """List channel-inbox deliveries, newest first.

        Args:
            workflow_id: Restrict to one workflow.
            status: Restrict to one lifecycle state.
            limit: Maximum rows.

        Returns:
            The matching deliveries.
        """
        async with self._lock:
            rows = [
                parked
                for parked in self._parked
                if (workflow_id is None or parked.workflow_id == workflow_id)
                and (status is None or parked.status is status)
            ]
            rows.sort(key=lambda parked: parked.created_at, reverse=True)
            return tuple(rows[:limit])

    async def replay_parked(
        self,
        parked_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> DeliveryDisposition:
        """Re-attempt routing of a parked or dead delivery.

        Args:
            parked_id: The delivery to replay.
            now: Current time in epoch seconds.
            attribution: Who asked and why, recorded in the audit log.

        Returns:
            The routing outcome, or ``unknown_key`` if no such delivery.
        """
        async with self._lock:
            disposition: DeliveryDisposition = "unknown_key"
            for index, parked in enumerate(self._parked):
                if parked.parked_id != parked_id:
                    continue
                if parked.status is ParkedStatus.DELIVERED:
                    disposition = "duplicate"
                    break
                self._parked[index] = dataclasses.replace(
                    parked, status=ParkedStatus.PENDING, reason=None, updated_at=now
                )
                disposition = self._route_parked_locked(index, now)
                break
            self._audit_locked(
                attribution,
                "replay_parked",
                parked_id,
                {"disposition": disposition},
                now,
            )
            return disposition

    def _audit_locked(
        self,
        attribution: Mapping[str, str] | None,
        action: str,
        target: str,
        detail: dict[str, Any],
        now: float,
    ) -> None:
        """Append one audit entry, with the lock held, when there is an actor.

        Args:
            attribution: Who asked and why; nothing is written without it.
            action: What was done.
            target: What it was done to.
            detail: Outcome and parameters.
            now: Current time in epoch seconds.
        """
        if not attribution:
            return
        self._audit.append(
            AuditEntry(
                audit_id=uuid.uuid4().hex,
                at=now,
                actor=attribution.get("actor", "unknown"),
                action=action,
                target=target,
                detail=detail,
                reason=attribution.get("reason"),
            )
        )

    async def list_audit(
        self, *, action: str | None = None, limit: int = 100
    ) -> tuple[AuditEntry, ...]:
        """List audited operator actions, newest first.

        Args:
            action: Restrict to one action name.
            limit: Maximum entries.

        Returns:
            The matching entries.
        """
        async with self._lock:
            rows = [
                entry
                for entry in reversed(self._audit)
                if action is None or entry.action == action
            ]
            return tuple(rows[:limit])

    async def set_schedule_paused(
        self,
        key: str,
        paused: bool,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> None:
        """Pause or resume a schedule, durably.

        Args:
            key: The schedule identity.
            paused: Whether the schedule should skip its occurrences.
            now: Current time in epoch seconds.
            attribution: Who asked and why, recorded in the audit log.
        """
        async with self._lock:
            if paused:
                self._paused_schedules.add(key)
            else:
                self._paused_schedules.discard(key)
            self._audit_locked(
                attribution,
                "pause_schedule" if paused else "resume_schedule",
                key,
                {"paused": paused},
                now,
            )

    async def paused_schedules(self) -> frozenset[str]:
        """The schedules currently paused.

        Returns:
            Their keys.
        """
        async with self._lock:
            return frozenset(self._paused_schedules)

    async def sweep_parked(self, now: float, ttl: float) -> int:
        """Turn PENDING deliveries older than a ttl into DEAD letters.

        Args:
            now: Current time in epoch seconds.
            ttl: Age in seconds beyond which PENDING is unclaimed.

        Returns:
            How many deliveries became dead letters.
        """
        async with self._lock:
            swept = 0
            for index, parked in enumerate(self._parked):
                if (
                    parked.status is ParkedStatus.PENDING
                    and now - parked.created_at > ttl
                ):
                    self._parked[index] = dataclasses.replace(
                        parked,
                        status=ParkedStatus.DEAD,
                        reason="unclaimed",
                        updated_at=now,
                    )
                    swept += 1
            return swept

    async def claim_next(
        self,
        now: float,
        *,
        lease_duration: float = DEFAULT_LEASE_DURATION,
        queues: tuple[str, ...] | None = None,
        release: str | None = None,
    ) -> Claim | None:
        """Claim the due frontier step of some runnable run.

        Args:
            now: Current time in epoch seconds.
            lease_duration: Seconds of renewal silence tolerated before the
                claim is treated as orphaned.
            queues: Queues this worker serves; None serves every queue. A run
                whose frontier sits on an unserved queue is skipped whole,
                because claiming a later slot would break its ordering.
            release: The claiming worker's release identity. A run pinned to
                a different release is skipped: it drains on the release that
                admitted it, so one run never mixes two releases' code.

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
                if (
                    release is not None
                    and run.release_id is not None
                    and run.release_id != release
                ):
                    # Pinned to another release: it drains on the workers
                    # that admitted it, never on this one.
                    continue
                if queues is not None and frontier.queue not in queues:
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
            # Past the deadline the only permitted outcome is TIMED_OUT,
            # and that is the sweep's transition, not this attempt's.
            _fence_deadline(run.run_id, run.deadline, now)
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
                self._append_events(
                    child_run.run_id,
                    _child_admission_events(child_run, child_step),
                    now,
                )
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
            if completion.run_status in TERMINAL_RUN_STATUSES:
                self._close_children(run.run_id, now)
            if completion.parent_arrival is not None:
                parent_id, ordinal, payload, dedupe_key = completion.parent_arrival
                self._apply_arrival(parent_id, ordinal, payload, dedupe_key, now)

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
        payload: Any,
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
            return self._deliver_locked(run_id, wait_key, dedupe_key, payload, now)

    def _deliver_locked(
        self,
        run_id: str,
        wait_key: str,
        dedupe_key: str,
        payload: Any,
        now: float,
    ) -> DeliveryDisposition:
        """Deliver with the store lock already held.

        Args:
            run_id: The receiving run.
            wait_key: The address the waiting slot declared.
            dedupe_key: Sender-supplied identity, making redelivery a no-op.
            payload: JSON-compatible payload to hand the resuming handler.
            now: Current time in epoch seconds.

        Returns:
            What the store did with the delivery.
        """
        run = self._runs.get(run_id)
        if run is None:
            return "unknown_run"
        if run.status in TERMINAL_RUN_STATUSES:
            return "run_terminal"
        if run.deadline is not None and run.deadline <= now:
            # The run can never execute a continuation: claims exclude
            # past-deadline runs and the sweep will finalize TIMED_OUT.
            # Answering "resolved" here would tell the sender their
            # decision was recorded when it is about to be discarded.
            return "expired"
        inbox = self._inbox.setdefault(run_id, {})
        if (run_id, wait_key, dedupe_key) in inbox:
            self._append_events(
                run_id,
                ((HistoryEventType.SIGNAL_DUPLICATE, {"wait_key": wait_key}),),
                now,
            )
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
        self._pending.setdefault(run_id, {}).setdefault(wait_key, []).append(payload)
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
            return self._apply_arrival(run_id, ordinal, payload, dedupe_key, now)

    def _apply_arrival(
        self,
        run_id: str,
        ordinal: int,
        payload: dict[str, Any],
        dedupe_key: str,
        now: float,
    ) -> DeliveryDisposition:
        """Count one arrival, with the lock already held.

        Args:
            run_id: The waiting parent run.
            ordinal: The join slot's ordinal.
            payload: The arriving result.
            dedupe_key: Identity of the arrival.
            now: Current time in epoch seconds.

        Returns:
            What the store did with the arrival.
        """
        run = self._runs.get(run_id)
        if run is None:
            return "unknown_run"
        if run.status in TERMINAL_RUN_STATUSES:
            return "run_terminal"
        if run.deadline is not None and run.deadline <= now:
            # The join can never run its continuation: the sweep is about to
            # finalize this parent TIMED_OUT and tombstone the slot. Counting
            # the arrival would record a step that cannot happen.
            return "expired"
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

    async def admit_flow(
        self,
        run: RunRecord,
        root_step: StepRecord,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
        gate: FlowGate,
        now: float,
    ) -> FlowAdmission:
        """Admit a run under a start policy, atomically.

        Args:
            run: The run record to create, carrying the flow key.
            root_step: The preallocated root mailbox slot.
            events: History events to append on creation.
            gate: The policy to enforce.
            now: Current time in epoch seconds.

        Returns:
            What was done, decided under the store lock.
        """
        async with self._lock:
            if run.request_key is not None:
                existing = self._dedupe.get((run.workflow_id, run.request_key))
                if existing is not None:
                    return FlowAdmission("deduplicated", existing)
            active = sorted(
                (
                    other
                    for other in self._runs.values()
                    if other.workflow_id == run.workflow_id
                    and other.flow_key == run.flow_key
                    and other.status not in TERMINAL_RUN_STATUSES
                ),
                key=lambda other: (other.created_at, other.run_id),
            )
            if gate.singleton_skip and active:
                return FlowAdmission("skipped", active[0].run_id)
            cancelled: list[str] = []
            if gate.singleton_cancel:
                for other in active:
                    self._runs[other.run_id] = dataclasses.replace(
                        other,
                        cancel_requested=True,
                        status=RunStatus.CANCELLING,
                        updated_at=now,
                    )
                    self._append_events(
                        other.run_id,
                        ((HistoryEventType.RUN_CANCEL_REQUESTED, {}),),
                        now,
                    )
                    cancelled.append(other.run_id)
            due_at = root_step.due_at
            if gate.rate_limit is not None:
                limit, window = gate.rate_limit
                started = sum(
                    1
                    for other in self._runs.values()
                    if other.workflow_id == run.workflow_id
                    and other.flow_key == run.flow_key
                    and other.created_at > now - window
                )
                if started >= limit:
                    return FlowAdmission("rejected", retry_after=window)
            if gate.throttle is not None:
                limit, window = gate.throttle
                starts = sorted(
                    (
                        max(steps[0].due_at, other.created_at)
                        for other in self._runs.values()
                        if other.workflow_id == run.workflow_id
                        and other.flow_key == run.flow_key
                        if (steps := self._steps.get(other.run_id))
                    ),
                    reverse=True,
                )
                previous = starts[limit - 1] if len(starts) >= limit else None
                if previous is not None and previous + window > now:
                    due_at = previous + window
            if gate.debounce is not None:
                pending = active[0] if active else None
                if pending is not None:
                    steps = self._steps.get(pending.run_id)
                    if steps and steps[0].status is StepStatus.READY:
                        # Latest wins: the burst's final payload is the one
                        # the debounced run eventually starts with, and the
                        # replacement rides the same transaction as the
                        # deadline extension.
                        steps[0] = dataclasses.replace(
                            steps[0],
                            args=root_step.args,
                            due_at=now + gate.debounce,
                            updated_at=now,
                        )
                        return FlowAdmission("coalesced", pending.run_id)
                due_at = now + gate.debounce
            if run.request_key is not None:
                self._dedupe[run.workflow_id, run.request_key] = run.run_id
            self._runs[run.run_id] = run
            self._steps[run.run_id] = [dataclasses.replace(root_step, due_at=due_at)]
            self._append_events(run.run_id, events, run.created_at)
            if run.request_key is not None:
                # Policy admission is still admission: early mail flushes on
                # this door exactly as on the plain one.
                self._flush_parked_locked(
                    run.workflow_id, run.request_key, run.run_id, run.created_at
                )
            return FlowAdmission("started", run.run_id, cancelled=tuple(cancelled))

    async def purge_runs(
        self,
        before: float,
        *,
        workflow_id: str | None = None,
        attribution: Mapping[str, str] | None = None,
    ) -> int:
        """Delete terminal runs not updated since a cutoff, and all their data.

        Args:
            before: Delete runs whose last update is older than this.
            workflow_id: Restrict to one workflow identity.
            attribution: Who asked and why, recorded in the audit log.

        Returns:
            How many runs were deleted.
        """
        async with self._lock:
            doomed = [
                run.run_id
                for run in self._runs.values()
                if run.status in TERMINAL_RUN_STATUSES
                and run.updated_at < before
                and (workflow_id is None or run.workflow_id == workflow_id)
            ]
            for run_id in doomed:
                run = self._runs.pop(run_id)
                self._steps.pop(run_id, None)
                self._history.pop(run_id, None)
                self._pending.pop(run_id, None)
                self._inbox.pop(run_id, None)
                for key in [k for k in self._substeps if k[0] == run_id]:
                    del self._substeps[key]
                if run.request_key is not None:
                    self._dedupe.pop((run.workflow_id, run.request_key), None)
            self._audit_locked(
                attribution,
                "purge_runs",
                workflow_id or "*",
                {"before": before, "deleted": len(doomed)},
                before,
            )
            return len(doomed)

    async def epoch_time(self) -> float | None:
        """This store never leaves one host, whose clock is the authority.

        Returns:
            None: the process clock is correct here.
        """
        return None

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

    async def request_cancel(
        self,
        run_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Record cancellation intent on a run.

        Args:
            run_id: The run to cancel.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".

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
                run_id,
                ((HistoryEventType.RUN_CANCEL_REQUESTED, dict(attribution or {})),),
                now,
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

    def _close_children(self, run_id: str, now: float) -> None:
        """Request cancellation of branches the closing run fanned out to.

        Called inside the transaction that takes a run terminal, so an
        operator cancelling a rollout durably stops the regional deploys it
        started -- not best-effort follow-up that dies with the worker.
        Grandchildren are not walked here: a marked child is control-pending
        the moment it drains (a run blocked on its own join holds no claim),
        so it finalizes and closes its own branches in turn.

        Args:
            run_id: The run reaching a terminal state.
            now: Current time in epoch seconds.
        """
        for child in self._runs.values():
            if (
                child.parent_run_id != run_id
                or child.parent_close == "abandon"
                or child.cancel_requested
                or child.status in TERMINAL_RUN_STATUSES
            ):
                # cancel_requested is durable and monotonic, so an
                # already-marked child has nothing left to write -- and
                # skipping it keeps a second close (a failed run later
                # skip-completed by an operator) from appending a duplicate
                # cancel-requested event to its history.
                continue
            self._runs[child.run_id] = dataclasses.replace(
                child,
                cancel_requested=True,
                status=RunStatus.CANCELLING,
                updated_at=now,
            )
            self._append_events(
                child.run_id,
                ((HistoryEventType.RUN_CANCEL_REQUESTED, {"cause": "parent_close"}),),
                now,
            )

    async def finalize_run(
        self,
        run_id: str,
        *,
        status: RunStatus,
        error: dict[str, Any] | None,
        event: HistoryEventType,
        now: float,
        result: Any = None,
        parent_arrival: tuple[str, int, dict[str, Any], str] | None = None,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Terminate a drained run and tombstone its unresolved slots.

        Args:
            run_id: The run to finalize.
            status: The terminal status to record.
            error: Error payload recorded on the run.
            event: The terminal history event type.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".
            result: Result to record, for an operator forcing completion.
            parent_arrival: When this run is a child, the arrival to deliver
                to its parent's join, applied in this same transaction.

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
                run,
                status=status,
                error=error,
                result=result if result is not None else run.result,
                updated_at=now,
            )
            events.append((
                event,
                {**({} if error is None else dict(error)), **(attribution or {})},
            ))
            self._append_events(run_id, events, now)
            self._close_children(run_id, now)
            if parent_arrival is not None:
                self._apply_arrival(*parent_arrival, now)
            return True

    async def skip_step(
        self,
        run_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Give up on a stuck step and let the run carry on past it.

        The operator's answer to a step that cannot succeed and is not worth
        failing the run over -- a vendor that retired an endpoint, a
        notification nobody needs any more. The step is marked SKIPPED, which
        is terminal and recorded as a decision rather than an outcome, and the
        run continues at whatever comes next. Legal only on a run stopped for
        attention or failure, so it can never race a working attempt.

        Args:
            run_id: The run to unstick.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".

        Returns:
            True if a blocking step was skipped.
        """
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None or run.status not in (
                RunStatus.NEEDS_ATTENTION,
                RunStatus.FAILED,
            ):
                return False
            steps = self._steps[run_id]
            for index, step in enumerate(steps):
                if step.status in (
                    StepStatus.FAILED,
                    StepStatus.TIMED_OUT,
                    StepStatus.NEEDS_ATTENTION,
                ):
                    steps[index] = dataclasses.replace(
                        step,
                        status=StepStatus.SKIPPED,
                        lease_expires_at=0.0,
                        updated_at=now,
                    )
                    restored = self._restore_tombstoned(steps, now)
                    # Skipping the last open slot leaves nothing to run, so
                    # the run is finished rather than pending forever -- being
                    # stuck in a new way is not a resolution.
                    open_left = any(
                        other.status not in TERMINAL_STEP_STATUSES for other in steps
                    )
                    events = [
                        (
                            HistoryEventType.STEP_SKIPPED,
                            {"ordinal": step.ordinal, **(attribution or {})},
                        ),
                        *(
                            (HistoryEventType.STEP_RESTORED, {"ordinal": ordinal})
                            for ordinal in restored
                        ),
                    ]
                    if not open_left:
                        events.append((HistoryEventType.RUN_COMPLETED, {}))
                    self._runs[run_id] = dataclasses.replace(
                        run,
                        status=RunStatus.PENDING if open_left else RunStatus.COMPLETED,
                        error=None,
                        updated_at=now,
                    )
                    self._append_events(run_id, events, now)
                    if not open_left:
                        # Completed by an operator's decision is still
                        # completed: branches are told to stop, and a parent
                        # joined on this run hears it finished instead of
                        # waiting forever on a run that no longer will.
                        self._close_children(run_id, now)
                        if run.parent_run_id is not None and (
                            run.parent_ordinal is not None
                        ):
                            self._apply_arrival(
                                run.parent_run_id,
                                run.parent_ordinal,
                                {
                                    "run_id": run_id,
                                    "status": RunStatus.COMPLETED.value,
                                    "result": None,
                                    "error": None,
                                },
                                run_id,
                                now,
                            )
                    return True
            return False

    async def retry_run(
        self,
        run_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Re-open a failed run at the step that failed.

        The operator's answer to a run that failed for a reason now fixed: the
        failed step runs again with a fresh attempt budget, and the failure
        stays in history rather than being erased.

        Args:
            run_id: The run to retry.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".

        Returns:
            True if a failed run was re-opened.
        """
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None or run.status is not RunStatus.FAILED:
                return False
            steps = self._steps[run_id]
            reopened = False
            for index, step in enumerate(steps):
                if step.status in (StepStatus.FAILED, StepStatus.TIMED_OUT):
                    steps[index] = dataclasses.replace(
                        step,
                        status=StepStatus.READY,
                        attempts=0,
                        due_at=now,
                        lease_expires_at=0.0,
                        error=None,
                        updated_at=now,
                    )
                    reopened = True
                    break
            if not reopened:
                return False
            restored = self._restore_tombstoned(steps, now)
            self._runs[run_id] = dataclasses.replace(
                run, status=RunStatus.PENDING, error=None, updated_at=now
            )
            self._append_events(
                run_id,
                (
                    (
                        HistoryEventType.RUN_RESUMED,
                        {"origin": "retry", **(attribution or {})},
                    ),
                    *(
                        (HistoryEventType.STEP_RESTORED, {"ordinal": ordinal})
                        for ordinal in restored
                    ),
                ),
                now,
            )
            return True

    @staticmethod
    def _restore_tombstoned(steps: list[StepRecord], now: float) -> list[int]:
        """Re-open the slots a run's stopping failure tombstoned.

        A terminal failure cancels every open slot behind it, so a
        preallocated chain's finalizer is CANCELLED the moment its
        predecessor fails. Retrying or skipping that predecessor promises to
        continue "from there" -- which is a lie unless the chain comes back.

        Within a run an operator can retry or skip -- FAILED or
        NEEDS_ATTENTION -- a CANCELLED slot can only be that failure's
        casualty: run-level cancellation ends in a CANCELLED run these
        actions refuse, and operator force-finalization leaves no failed or
        suspended step for them to target. Nothing independently cancelled is
        revived because nothing independently cancelled can be here.

        Args:
            steps: The run's mailbox, mutated in place.
            now: Current time in epoch seconds.

        Returns:
            The restored ordinals, in order.
        """
        restored: list[int] = []
        for index, step in enumerate(steps):
            if step.status is StepStatus.CANCELLED:
                # A wait or join comes back as what it was -- BLOCKED, with
                # its arrival count and deadline intact -- never as READY:
                # restored-as-READY it would run immediately with a missing
                # or partial payload. Plain slots keep their own due_at too,
                # so a restored delay still waits out its delay instead of
                # firing the moment an operator retries.
                waiting = step.wait_key is not None
                steps[index] = dataclasses.replace(
                    step,
                    status=StepStatus.BLOCKED if waiting else StepStatus.READY,
                    attempts=0,
                    lease_expires_at=0.0,
                    error=None,
                    updated_at=now,
                )
                restored.append(step.ordinal)
        return restored

    async def resume_run(
        self,
        run_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Re-open a suspended run so its frontier step runs again.

        Args:
            run_id: The run to resume.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".

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
            self._append_events(
                run_id, ((HistoryEventType.RUN_RESUMED, dict(attribution or {})),), now
            )
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
                        # Replaced from the CURRENT record, not the loop's
                        # snapshot: when a parent and its child both exhaust
                        # in one pass, the parent's cascade has already set
                        # cancel_requested on this child, and a snapshot
                        # rebuild would silently revert it -- letting a later
                        # retry revive a branch whose parent is dead. The SQL
                        # stores update columns in place and keep the flag;
                        # this is the same semantics.
                        self._runs[run.run_id] = dataclasses.replace(
                            self._runs[run.run_id],
                            status=RunStatus.FAILED,
                            error={"reason": "recovery_budget_exhausted"},
                            updated_at=now,
                        )
                        # Exhaustion is a failure, and failure closes the run
                        # completely: open slots tombstoned so a dead run
                        # surfaces no wake times, branches told to stop so
                        # children do not keep working for a parent that no
                        # longer exists.
                        tombstoned = []
                        for other in list(steps):
                            if (
                                other.ordinal != step.ordinal
                                and other.status not in TERMINAL_STEP_STATUSES
                            ):
                                steps[other.ordinal] = dataclasses.replace(
                                    other,
                                    status=StepStatus.CANCELLED,
                                    updated_at=now,
                                )
                                tombstoned.append(other.ordinal)
                        self._append_events(
                            run.run_id,
                            tuple(
                                (
                                    HistoryEventType.STEP_TOMBSTONED,
                                    {"ordinal": ordinal},
                                )
                                for ordinal in tombstoned
                            ),
                            now,
                        )
                        self._close_children(run.run_id, now)
                        failed.append(run.run_id)
                        if run.parent_run_id is not None and (
                            run.parent_ordinal is not None
                        ):
                            self._apply_arrival(
                                run.parent_run_id,
                                run.parent_ordinal,
                                {
                                    "run_id": run.run_id,
                                    "status": RunStatus.FAILED.value,
                                    "result": None,
                                    "error": {"reason": "recovery_budget_exhausted"},
                                },
                                run.run_id,
                                now,
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
                        break
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

    async def count_runs(self, query: RunQuery) -> int:
        """Count runs matching a query.

        The count ignores ``limit`` and ``created_before``: those page a
        listing, and an aggregate is not a page. Everything else filters as
        it does for ``list_runs``, so a count and a listing always describe
        the same set.

        Args:
            query: The filters to apply.

        Returns:
            How many runs match.
        """
        counted = dataclasses.replace(query, created_before=None)
        async with self._lock:
            return sum(1 for run in self._runs.values() if _matches_query(run, counted))

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

    async def record_substep(
        self, run_id: str, ordinal: int, epoch: int, key: str, payload: Any, now: float
    ) -> bool:
        """Durably record one substep result inside a claimed attempt.

        The write is fenced on the step's claim epoch: an attempt whose lease
        was reclaimed must not pollute the journal a newer attempt is reading.
        The first write for a key wins, so a duplicate is a no-op that still
        reports success -- memoization reads before it writes, so a duplicate
        only means two racing writers agreed.

        Args:
            run_id: The owning run.
            ordinal: The mailbox slot being executed.
            epoch: The claim fence of the writing attempt.
            key: The substep's memoization key, unique within the step.
            payload: JSON-compatible result to record.
            now: Current time in epoch seconds.

        Returns:
            True when recorded (or already recorded); False when the writer
            was fenced and must stop.
        """
        async with self._lock:
            steps = self._steps.get(run_id)
            if steps is None or ordinal >= len(steps):
                return False
            step = steps[ordinal]
            if step.status is not StepStatus.CLAIMED or step.epoch != epoch:
                return False
            journal = self._substeps.setdefault((run_id, ordinal), {})
            if key not in journal:
                journal[key] = copy.deepcopy(payload)
                self._append_events(
                    run_id,
                    (
                        (
                            HistoryEventType.SUBSTEP_RECORDED,
                            {"ordinal": ordinal, "key": key},
                        ),
                    ),
                    now,
                )
            return True

    async def get_substeps(self, run_id: str, ordinal: int) -> dict[str, Any]:
        """Load the recorded substep results of one step.

        Args:
            run_id: The owning run.
            ordinal: The mailbox slot.

        Returns:
            Recorded payloads by key, in recording order.
        """
        async with self._lock:
            journal = self._substeps.get((run_id, ordinal), {})
            return {key: copy.deepcopy(value) for key, value in journal.items()}

    async def get_history(self, run_id: str) -> tuple[HistoryEvent, ...]:
        """Load a run's append-only history in sequence order.

        Args:
            run_id: The run identity.

        Returns:
            The history events.
        """
        async with self._lock:
            return tuple(self._history.get(run_id, ()))

    async def read_schedule_cursor(self, key: str) -> float | None:
        """Read where a schedule's catch-up last reached.

        Args:
            key: The schedule identity, "{workflow_id}:{handler_id}".

        Returns:
            The last swept time, or None when the schedule is new here.
        """
        async with self._lock:
            return self._schedule_cursors.get(key)

    async def write_schedule_cursor(self, key: str, at: float) -> None:
        """Record where a schedule's catch-up has now reached.

        Persisting this is what makes a restart resume rather than silently
        skip: an in-memory cursor reseeded at startup treats every occurrence
        during the downtime as if it had already fired.

        Args:
            key: The schedule identity, "{workflow_id}:{handler_id}".
            at: The time swept up to, in epoch seconds.
        """
        async with self._lock:
            # Never move backwards: two workers sweeping out of order would
            # otherwise rewind the cursor and re-scan ground already covered.
            # Re-scanning is harmless (occurrences dedupe on their request
            # key) but it is pure waste, and a cursor that can go back is not
            # a position anyone can reason about.
            self._schedule_cursors[key] = max(at, self._schedule_cursors.get(key, at))

    async def next_due(
        self, now: float, *, queues: tuple[str, ...] | None = None
    ) -> float | None:
        """Earliest future time any runnable run becomes claimable.

        Args:
            now: Current time in epoch seconds.
            queues: Queues this worker serves; None serves every queue.

        Returns:
            The epoch time, or None when no future work is scheduled.
        """
        async with self._lock:
            due_times = []
            for run in self._runs.values():
                if not _run_is_runnable(run, now):
                    continue
                frontier = _frontier(self._steps[run.run_id])
                if (
                    frontier is not None
                    and queues is not None
                    and frontier.queue not in queues
                ):
                    continue
                wake_at = None if frontier is None else step_wake_at(frontier)
                if wake_at is not None:
                    due_times.append(wake_at)
            return min(due_times) if due_times else None


SCHEMA_VERSION: Final = 7
"""Stamped into PRAGMA user_version; bump when _SCHEMA or migrations change."""

DATABASE_ENV: Final = "REFLEX_WORKFLOW_DATABASE"
DEFAULT_DB_FILENAME: Final = "workflow.db"


def resolve_store(target: str | None = None) -> RunStore:
    """Open the store a deployment's configuration names.

    This is the one place the app, the CLI, and a hosting platform agree on
    what a database target means: a ``postgres://`` or ``postgresql://`` URL
    opens the Postgres store, anything else is a path to a SQLite file, and
    with nothing configured the default is a SQLite file next to the app.
    Hosting sets ``REFLEX_WORKFLOW_DATABASE`` and every surface follows it,
    with no code changes in the app.

    Args:
        target: Connection URL or SQLite path. None reads the environment,
            then falls back to the local default.

    Returns:
        The store.
    """
    import os

    resolved = target or os.environ.get(DATABASE_ENV)
    if resolved is not None and resolved.startswith(("postgres://", "postgresql://")):
        from reflex.workflow.postgres import PostgresRunStore

        return PostgresRunStore(resolved)
    return SqliteRunStore(resolved or Path.cwd() / DEFAULT_DB_FILENAME)


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
    parent_close TEXT NOT NULL DEFAULT 'cancel',
    request_key TEXT,
    labels TEXT,
    deadline REAL,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    release_id TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_workers (
    worker_id TEXT PRIMARY KEY,
    release_id TEXT,
    queues TEXT NOT NULL,
    capacity INTEGER NOT NULL,
    started_at REAL NOT NULL,
    heartbeat_at REAL NOT NULL
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
    queue TEXT NOT NULL DEFAULT 'default',
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
CREATE TABLE IF NOT EXISTS workflow_schedules (
    key TEXT PRIMARY KEY,
    at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_substeps (
    run_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    key TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (run_id, ordinal, key)
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
CREATE INDEX IF NOT EXISTS idx_workflow_steps_wake
    ON workflow_steps (status, due_at, queue);
CREATE INDEX IF NOT EXISTS idx_workflow_inbox_pending
    ON workflow_inbox (run_id, wait_key, status, seq);
CREATE TABLE IF NOT EXISTS workflow_channel_inbox (
    parked_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    correlation_key TEXT NOT NULL,
    dedupe_key TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT,
    run_id TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE (workflow_id, channel, correlation_key, dedupe_key)
);
CREATE INDEX IF NOT EXISTS idx_workflow_channel_inbox_route
    ON workflow_channel_inbox (workflow_id, correlation_key, status);
CREATE TABLE IF NOT EXISTS workflow_audit (
    audit_id TEXT PRIMARY KEY,
    at REAL NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    detail TEXT NOT NULL,
    reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_workflow_audit_at ON workflow_audit (at);
CREATE TABLE IF NOT EXISTS workflow_schedule_state (
    key TEXT PRIMARY KEY,
    paused INTEGER NOT NULL,
    updated_at REAL NOT NULL
);
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
    (
        "queue",
        "ALTER TABLE workflow_steps ADD COLUMN queue TEXT NOT NULL DEFAULT 'default'",
    ),
)

_RUN_MIGRATIONS: Final = (
    ("release_id", "ALTER TABLE workflow_runs ADD COLUMN release_id TEXT"),
    ("flow_key", "ALTER TABLE workflow_runs ADD COLUMN flow_key TEXT"),
    ("parent_run_id", "ALTER TABLE workflow_runs ADD COLUMN parent_run_id TEXT"),
    ("parent_ordinal", "ALTER TABLE workflow_runs ADD COLUMN parent_ordinal INTEGER"),
    (
        "parent_close",
        (
            "ALTER TABLE workflow_runs ADD COLUMN parent_close TEXT NOT NULL"
            " DEFAULT 'cancel'"
        ),
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
        flow_key=row["flow_key"],
        parent_run_id=row["parent_run_id"],
        parent_close=row["parent_close"] or "cancel",
        parent_ordinal=row["parent_ordinal"],
        request_key=row["request_key"],
        labels=_load(row["labels"]),
        release_id=row["release_id"],
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
        queue=row["queue"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _fence_deadline(run_id: str, deadline: float | None, now: float) -> None:
    """Refuse a commit for a run already past its deadline.

    Args:
        run_id: The committing run.
        deadline: Its deadline, when it has one.
        now: Current time in epoch seconds.

    Raises:
        DeadlinePassedError: When the deadline has passed.
    """
    if deadline is not None and deadline <= now:
        msg = f"Run {run_id} passed its deadline before commit."
        raise DeadlinePassedError(msg)


def _child_admission_events(
    child_run: RunRecord, child_step: StepRecord
) -> tuple[tuple[HistoryEventType, dict[str, Any]], ...]:
    """The admission history a fan-out child gets, same as any run.

    Children are advertised as ordinary runs, so a history that begins at
    attempt_started -- with no admission, no scheduling -- breaks the
    invariant every other reader relies on, and a metrics observer counting
    runs_started reports one start for a four-run graph.

    Args:
        child_run: The child being created.
        child_step: Its root slot.

    Returns:
        The admission events to record with the creating transaction.
    """
    return (
        (
            HistoryEventType.RUN_ADMITTED,
            {
                "handler_id": child_step.handler_id,
                "request_key": child_run.request_key,
            },
        ),
        (
            HistoryEventType.STEP_SCHEDULED,
            {"ordinal": child_step.ordinal, "handler_id": child_step.handler_id},
        ),
    )


def _audit_from_row(row: Mapping[str, Any]) -> AuditEntry:
    """Build an audit entry from a database row.

    Args:
        row: The ``workflow_audit`` row.

    Returns:
        The entry.
    """
    return AuditEntry(
        audit_id=row["audit_id"],
        at=row["at"],
        actor=row["actor"],
        action=row["action"],
        target=row["target"],
        detail=json.loads(row["detail"]),
        reason=row["reason"],
    )


def _parked_from_row(row: Mapping[str, Any]) -> ParkedDelivery:
    """Build a parked-delivery record from a database row.

    Args:
        row: The ``workflow_channel_inbox`` row.

    Returns:
        The record.
    """
    return ParkedDelivery(
        parked_id=row["parked_id"],
        workflow_id=row["workflow_id"],
        channel=row["channel"],
        correlation_key=row["correlation_key"],
        dedupe_key=row["dedupe_key"],
        payload=json.loads(row["payload"]),
        status=ParkedStatus(row["status"]),
        reason=row["reason"],
        run_id=row["run_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _sqlite_frontier_query(
    select: str,
    now: float,
    queues: tuple[str, ...] | None,
    *,
    due_only: bool,
    order: str,
    limit: int,
    release: str | None = None,
) -> tuple[str, tuple[Any, ...]]:
    """Build the query for claimable-or-waking frontier steps.

    The shape both the claimer and the sleep bound need: steps whose status
    can wake, on runnable runs, that are their run's frontier -- the lowest
    unresolved ordinal -- filtered and ordered so the wake index does the
    work and a LIMIT stops the scan. Loading every run and walking its steps
    in Python made an idle worker's poll linear in the number of sleeping
    runs, which at ten thousand of them was ~114ms per poll and half a core
    doing nothing.

    Args:
        select: The select list, over alias ``s``.
        now: Current time in epoch seconds.
        queues: Queues served; None serves every queue.
        due_only: Restrict to steps claimable right now; otherwise any step a
            clock event alone can make claimable, however far out.
        order: ORDER BY expression.
        limit: Maximum rows.
        release: The claiming worker's release; a run pinned to a different
            release is skipped, never claimed.

    Returns:
        The SQL and its parameters.
    """
    claimable = tuple(s.value for s in CLAIMABLE_STEP_STATUSES)
    terminal_steps = tuple(s.value for s in TERMINAL_STEP_STATUSES)
    terminal_runs = tuple(s.value for s in TERMINAL_RUN_STATUSES)
    marks = lambda values: ",".join("?" * len(values))  # noqa: E731
    if due_only:
        waking = (
            f"((s.status IN ({marks(claimable)}) AND s.due_at <= ?)"
            " OR (s.status = ? AND s.due_at > 0 AND s.due_at <= ?))"
        )
        waking_params = (*claimable, now, StepStatus.BLOCKED.value, now)
    else:
        waking = (
            f"(s.status IN ({marks(claimable)}) OR (s.status = ? AND s.due_at > 0))"
        )
        waking_params = (*claimable, StepStatus.BLOCKED.value)
    queue_sql = f" AND s.queue IN ({marks(queues)})" if queues is not None else ""
    queue_params = tuple(queues) if queues is not None else ()
    release_sql = (
        " AND (r.release_id IS NULL OR r.release_id = ?)" if release is not None else ""
    )
    release_params = (release,) if release is not None else ()
    sql = (
        f"SELECT {select} FROM workflow_steps s"
        " JOIN workflow_runs r ON r.run_id = s.run_id"
        f" WHERE {waking}"
        f" AND r.status NOT IN ({marks(terminal_runs)})"
        " AND r.status != ? AND r.cancel_requested = 0"
        " AND (r.deadline IS NULL OR r.deadline > ?)"
        f"{release_sql}"
        " AND NOT EXISTS (SELECT 1 FROM workflow_steps x"
        " WHERE x.run_id = s.run_id AND x.ordinal < s.ordinal"
        f" AND x.status NOT IN ({marks(terminal_steps)}))"
        f"{queue_sql} ORDER BY {order} LIMIT {int(limit)}"
    )
    params = (
        *waking_params,
        *terminal_runs,
        RunStatus.NEEDS_ATTENTION.value,
        now,
        *release_params,
        *terminal_steps,
        *queue_params,
    )
    return sql, params


def _sqlite_run_filters(query: RunQuery) -> tuple[str, tuple[Any, ...]]:
    """Build the WHERE clause a run query means, for SQLite.

    Shared by listing and counting so the two can never disagree about what
    matches.

    Args:
        query: The filters to apply; ``limit`` is not one of them.

    Returns:
        The clause (empty when nothing filters) and its parameters.
    """
    clauses: list[str] = []
    params: list[Any] = []
    if query.workflow_id is not None:
        clauses.append("workflow_id = ?")
        params.append(query.workflow_id)
    if query.definition_digest is not None:
        clauses.append("definition_digest = ?")
        params.append(query.definition_digest)
    if query.release_id is not None:
        clauses.append("release_id = ?")
        params.append(query.release_id)
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
    return where, tuple(params)


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
        # A current database opens without taking any write lock: DDL only
        # runs when the stamped schema version is behind. An operator's
        # list/stats/show against a busy worker used to fail with "database
        # is locked" purely because opening the store ran CREATEs and an
        # immediate-mode migration it did not need.
        current = self._db.execute("PRAGMA user_version").fetchone()[0]
        if current < SCHEMA_VERSION:
            # Strictly upward: a stamp from a newer binary means a newer
            # schema owns this file, and rerunning our DDL would stamp the
            # OLDER version over it -- a silent downgrade. Newer schemas are
            # additive by policy, so reading them with this binary is safe.
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
            self._db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self._db.execute("COMMIT")
        except BaseException:
            self._db.execute("ROLLBACK")
            raise

    def close(self) -> None:
        """Close the backing database connection.

        Under the store's lock: every operation runs its SQL holding it, and
        an operation abandoned by a cancelled awaiter is still executing on
        its worker thread. Closing the connection out from under that thread
        is a segfault in the sqlite3 C layer, not an exception -- taking the
        lock makes close wait out whatever is mid-statement.
        """
        with self._lock:
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
            " flow_key, parent_run_id, parent_ordinal, parent_close,"
            " request_key, labels, deadline, cancel_requested, release_id,"
            " created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                run.parent_close,
                run.request_key,
                _dump(run.labels),
                run.deadline,
                int(run.cancel_requested),
                run.release_id,
                run.created_at,
                run.updated_at,
            ),
        )

    def _close_children_sql(self, run_id: str, now: float) -> None:
        """Request cancellation of branches the closing run fanned out to.

        Called inside the transaction that takes a run terminal, so an
        operator cancelling a rollout durably stops the regional deploys it
        started -- not best-effort follow-up that dies with the worker.
        Grandchildren are not walked here: a marked child is control-pending
        the moment it drains (a run blocked on its own join holds no claim),
        so it finalizes and closes its own branches in turn.

        Args:
            run_id: The run reaching a terminal state.
            now: Current time in epoch seconds.
        """
        terminal = tuple(s.value for s in TERMINAL_RUN_STATUSES)
        closing = self._db.execute(
            "UPDATE workflow_runs SET cancel_requested = 1, status = ?,"
            " updated_at = ? WHERE parent_run_id = ? AND parent_close <> 'abandon'"
            " AND NOT cancel_requested"
            f" AND status NOT IN ({','.join('?' * len(terminal))})"
            " RETURNING run_id",
            (RunStatus.CANCELLING.value, now, run_id, *terminal),
        ).fetchall()
        for row in closing:
            self._append_events(
                row["run_id"],
                ((HistoryEventType.RUN_CANCEL_REQUESTED, {"cause": "parent_close"}),),
                now,
            )

    def _insert_step(self, step: StepRecord) -> None:
        """Insert a step row inside the current transaction.

        Args:
            step: The step record.
        """
        self._db.execute(
            "INSERT INTO workflow_steps (run_id, ordinal, handler_id, status, args,"
            " attempts, recoveries, due_at, epoch, lease_expires_at, wait_key,"
            " join_expected, join_arrived, error, origin, queue, created_at,"
            " updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                step.queue,
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

        Roots with a start policy are admitted through ``admit_flow``, where
        the whole policy decision shares the admitting transaction.

        Args:
            run: The run record to create.
            root_step: The preallocated root mailbox slot.
            events: History events to append on creation.

        Returns:
            Whether the run was created, and the authoritative run id.
        """

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
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
                    if run.request_key is not None:
                        # Deliveries that arrived before this run did, flushed
                        # inside the admitting transaction: a crash cannot
                        # separate "the run exists" from "its early mail
                        # reached it".
                        self._flush_parked_in_txn(
                            run.workflow_id,
                            run.request_key,
                            run.run_id,
                            run.created_at,
                        )
                    self._db.execute("COMMIT")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise
                return True, run.run_id

        return await asyncio.to_thread(work)

    def _flush_parked_in_txn(
        self, workflow_id: str, request_key: str, run_id: str, now: float
    ) -> None:
        """Deliver PENDING channel-inbox rows to a freshly admitted run.

        Args:
            workflow_id: The workflow identity.
            request_key: The admission key, matched against correlation keys.
            run_id: The run that now exists.
            now: Current time in epoch seconds.
        """
        rows = self._db.execute(
            "SELECT parked_id, channel, dedupe_key, payload FROM"
            " workflow_channel_inbox WHERE workflow_id = ? AND"
            " correlation_key = ? AND status = ? ORDER BY created_at",
            (workflow_id, request_key, ParkedStatus.PENDING.value),
        ).fetchall()
        for row in rows:
            disposition = self._deliver_in_txn(
                run_id,
                f"sig:{row['channel']}",
                row["dedupe_key"],
                json.loads(row["payload"]),
                now,
            )
            delivered = disposition in ("resolved", "buffered", "duplicate")
            self._db.execute(
                "UPDATE workflow_channel_inbox SET status = ?, reason = ?,"
                " run_id = ?, updated_at = ? WHERE parked_id = ?",
                (
                    ParkedStatus.DELIVERED.value
                    if delivered
                    else ParkedStatus.DEAD.value,
                    None if delivered else disposition,
                    run_id if delivered else None,
                    now,
                    row["parked_id"],
                ),
            )

    def _route_parked_in_txn(self, parked_id: str, now: float) -> DeliveryDisposition:
        """Route one PENDING channel-inbox row inside an open transaction.

        Args:
            parked_id: The row to route.
            now: Current time in epoch seconds.

        Returns:
            The routing outcome.
        """
        row = self._db.execute(
            "SELECT workflow_id, channel, correlation_key, dedupe_key, payload"
            " FROM workflow_channel_inbox WHERE parked_id = ?",
            (parked_id,),
        ).fetchone()
        target = self._db.execute(
            "SELECT run_id FROM workflow_dedupe WHERE workflow_id = ?"
            " AND request_key = ?",
            (row["workflow_id"], row["correlation_key"]),
        ).fetchone()
        if target is None:
            return "parked"
        disposition = self._deliver_in_txn(
            target["run_id"],
            f"sig:{row['channel']}",
            row["dedupe_key"],
            json.loads(row["payload"]),
            now,
        )
        delivered = disposition in ("resolved", "buffered", "duplicate")
        self._db.execute(
            "UPDATE workflow_channel_inbox SET status = ?, reason = ?, run_id = ?,"
            " updated_at = ? WHERE parked_id = ?",
            (
                ParkedStatus.DELIVERED.value if delivered else ParkedStatus.DEAD.value,
                None if delivered else disposition,
                target["run_id"] if delivered else None,
                now,
                parked_id,
            ),
        )
        return disposition if delivered else "dead_letter"

    async def register_worker(self, worker: WorkerRecord) -> None:
        """Record (or refresh) a worker's registration.

        Args:
            worker: The worker's identity, release, queues, and capacity.
        """

        def work() -> None:
            """Run the operation on the worker thread."""
            with self._lock:
                self._db.execute(
                    "INSERT INTO workflow_workers (worker_id, release_id,"
                    " queues, capacity, started_at, heartbeat_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)"
                    " ON CONFLICT (worker_id) DO UPDATE SET release_id ="
                    " excluded.release_id, queues = excluded.queues,"
                    " capacity = excluded.capacity,"
                    " heartbeat_at = excluded.heartbeat_at",
                    (
                        worker.worker_id,
                        worker.release_id,
                        json.dumps(list(worker.queues)),
                        worker.capacity,
                        worker.started_at,
                        worker.heartbeat_at,
                    ),
                )

        await asyncio.to_thread(work)

    async def heartbeat_worker(self, worker_id: str, now: float) -> None:
        """Refresh a worker's sign of life.

        Args:
            worker_id: The worker.
            now: Current time in epoch seconds.
        """

        def work() -> None:
            """Run the operation on the worker thread."""
            with self._lock:
                self._db.execute(
                    "UPDATE workflow_workers SET heartbeat_at = ? WHERE worker_id = ?",
                    (now, worker_id),
                )

        await asyncio.to_thread(work)

    async def deregister_worker(self, worker_id: str) -> None:
        """Remove a worker that shut down cleanly.

        Args:
            worker_id: The worker.
        """

        def work() -> None:
            """Run the operation on the worker thread."""
            with self._lock:
                self._db.execute(
                    "DELETE FROM workflow_workers WHERE worker_id = ?",
                    (worker_id,),
                )

        await asyncio.to_thread(work)

    async def list_workers(self) -> tuple[WorkerRecord, ...]:
        """List registered workers, most recently started first.

        Returns:
            The registrations.
        """

        def work() -> tuple[WorkerRecord, ...]:
            """Run the operation on the worker thread.

            Returns:
                The registrations.
            """
            with self._lock:
                rows = self._db.execute(
                    "SELECT * FROM workflow_workers ORDER BY started_at DESC"
                ).fetchall()
            return tuple(
                WorkerRecord(
                    worker_id=row["worker_id"],
                    release_id=row["release_id"],
                    queues=tuple(json.loads(row["queues"])),
                    capacity=row["capacity"],
                    started_at=row["started_at"],
                    heartbeat_at=row["heartbeat_at"],
                )
                for row in rows
            )

        return await asyncio.to_thread(work)

    async def ingest_channel_delivery(
        self,
        workflow_id: str,
        channel: str,
        correlation_key: str,
        dedupe_key: str,
        payload: Any,
        now: float,
    ) -> DeliveryDisposition:
        """Durably accept a correlated provider event, exactly once.

        Args:
            workflow_id: The workflow whose channel the event addresses.
            channel: The channel name.
            correlation_key: The business key naming the target run.
            dedupe_key: The provider's event identity.
            payload: The canonical event payload.
            now: Current time in epoch seconds.

        Returns:
            The routing outcome.
        """

        def work() -> DeliveryDisposition:
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
            """
            parked_id = uuid.uuid4().hex
            with self._lock:
                self._db.execute("BEGIN IMMEDIATE")
                try:
                    inserted = self._db.execute(
                        "INSERT INTO workflow_channel_inbox (parked_id,"
                        " workflow_id, channel, correlation_key, dedupe_key,"
                        " payload, status, created_at, updated_at)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
                        " ON CONFLICT DO NOTHING",
                        (
                            parked_id,
                            workflow_id,
                            channel,
                            correlation_key,
                            dedupe_key,
                            json.dumps(payload),
                            ParkedStatus.PENDING.value,
                            now,
                            now,
                        ),
                    )
                    if inserted.rowcount == 0:
                        # The event id is the identity: a provider redelivery
                        # and a crash-after-ack replay both land here.
                        self._db.execute("COMMIT")
                        return "duplicate"
                    disposition = self._route_parked_in_txn(parked_id, now)
                    self._db.execute("COMMIT")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise
                return disposition

        return await asyncio.to_thread(work)

    async def list_parked(
        self,
        *,
        workflow_id: str | None = None,
        status: ParkedStatus | None = None,
        limit: int = 100,
    ) -> tuple[ParkedDelivery, ...]:
        """List channel-inbox deliveries, newest first.

        Args:
            workflow_id: Restrict to one workflow.
            status: Restrict to one lifecycle state.
            limit: Maximum rows.

        Returns:
            The matching deliveries.
        """

        def work() -> tuple[ParkedDelivery, ...]:
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
            """
            clauses, params = [], []
            if workflow_id is not None:
                clauses.append("workflow_id = ?")
                params.append(workflow_id)
            if status is not None:
                clauses.append("status = ?")
                params.append(status.value)
            where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
            with self._lock:
                rows = self._db.execute(
                    f"SELECT * FROM workflow_channel_inbox{where}"
                    " ORDER BY created_at DESC LIMIT ?",
                    (*params, limit),
                ).fetchall()
            return tuple(_parked_from_row(row) for row in rows)

        return await asyncio.to_thread(work)

    async def replay_parked(
        self,
        parked_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> DeliveryDisposition:
        """Re-attempt routing of a parked or dead delivery.

        Args:
            parked_id: The delivery to replay.
            now: Current time in epoch seconds.
            attribution: Who asked and why, recorded in the audit log.

        Returns:
            The routing outcome, or ``unknown_key`` if no such delivery.
        """

        def work() -> DeliveryDisposition:
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
            """
            with self._lock:
                self._db.execute("BEGIN IMMEDIATE")
                try:
                    row = self._db.execute(
                        "SELECT status FROM workflow_channel_inbox WHERE parked_id = ?",
                        (parked_id,),
                    ).fetchone()
                    if row is None:
                        self._audit_sql(
                            attribution,
                            "replay_parked",
                            parked_id,
                            {"disposition": "unknown_key"},
                            now,
                        )
                        self._db.execute("COMMIT")
                        return "unknown_key"
                    if row["status"] == ParkedStatus.DELIVERED.value:
                        # Replaying what already reached its run must never
                        # signal twice.
                        self._audit_sql(
                            attribution,
                            "replay_parked",
                            parked_id,
                            {"disposition": "duplicate"},
                            now,
                        )
                        self._db.execute("COMMIT")
                        return "duplicate"
                    self._db.execute(
                        "UPDATE workflow_channel_inbox SET status = ?,"
                        " reason = NULL, updated_at = ? WHERE parked_id = ?",
                        (ParkedStatus.PENDING.value, now, parked_id),
                    )
                    disposition = self._route_parked_in_txn(parked_id, now)
                    self._audit_sql(
                        attribution,
                        "replay_parked",
                        parked_id,
                        {"disposition": disposition},
                        now,
                    )
                    self._db.execute("COMMIT")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise
                return disposition

        return await asyncio.to_thread(work)

    async def sweep_parked(self, now: float, ttl: float) -> int:
        """Turn PENDING deliveries older than a ttl into DEAD letters.

        Args:
            now: Current time in epoch seconds.
            ttl: Age in seconds beyond which PENDING is unclaimed.

        Returns:
            How many deliveries became dead letters.
        """

        def work() -> int:
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
            """
            with self._lock:
                cursor = self._db.execute(
                    "UPDATE workflow_channel_inbox SET status = ?,"
                    " reason = 'unclaimed', updated_at = ?"
                    " WHERE status = ? AND created_at < ?",
                    (
                        ParkedStatus.DEAD.value,
                        now,
                        ParkedStatus.PENDING.value,
                        now - ttl,
                    ),
                )
                return cursor.rowcount

        return await asyncio.to_thread(work)

    def _audit_sql(
        self,
        attribution: Mapping[str, str] | None,
        action: str,
        target: str,
        detail: dict[str, Any],
        now: float,
    ) -> None:
        """Insert one audit entry inside the current transaction, if attributed.

        Args:
            attribution: Who asked and why; nothing is written without it.
            action: What was done.
            target: What it was done to.
            detail: Outcome and parameters.
            now: Current time in epoch seconds.
        """
        if not attribution:
            return
        self._db.execute(
            "INSERT INTO workflow_audit (audit_id, at, actor, action, target,"
            " detail, reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                uuid.uuid4().hex,
                now,
                attribution.get("actor", "unknown"),
                action,
                target,
                json.dumps(detail),
                attribution.get("reason"),
            ),
        )

    async def list_audit(
        self, *, action: str | None = None, limit: int = 100
    ) -> tuple[AuditEntry, ...]:
        """List audited operator actions, newest first.

        Args:
            action: Restrict to one action name.
            limit: Maximum entries.

        Returns:
            The matching entries.
        """

        def work() -> tuple[AuditEntry, ...]:
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
            """
            where = " WHERE action = ?" if action is not None else ""
            params: tuple = (action, limit) if action is not None else (limit,)
            with self._lock:
                rows = self._db.execute(
                    f"SELECT * FROM workflow_audit{where}"
                    " ORDER BY at DESC, rowid DESC LIMIT ?",
                    params,
                ).fetchall()
            return tuple(_audit_from_row(row) for row in rows)

        return await asyncio.to_thread(work)

    async def set_schedule_paused(
        self,
        key: str,
        paused: bool,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> None:
        """Pause or resume a schedule, durably.

        Args:
            key: The schedule identity.
            paused: Whether the schedule should skip its occurrences.
            now: Current time in epoch seconds.
            attribution: Who asked and why, recorded in the audit log.
        """

        def work() -> None:
            """Run the operation on the worker thread."""
            with self._lock:
                self._db.execute("BEGIN IMMEDIATE")
                try:
                    self._db.execute(
                        "INSERT INTO workflow_schedule_state (key, paused, updated_at)"
                        " VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET"
                        " paused = excluded.paused, updated_at = excluded.updated_at",
                        (key, int(paused), now),
                    )
                    self._audit_sql(
                        attribution,
                        "pause_schedule" if paused else "resume_schedule",
                        key,
                        {"paused": paused},
                        now,
                    )
                    self._db.execute("COMMIT")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise

        await asyncio.to_thread(work)

    async def paused_schedules(self) -> frozenset[str]:
        """The schedules currently paused.

        Returns:
            Their keys.
        """

        def work() -> frozenset[str]:
            """Run the operation on the worker thread.

            Returns:
                The paused keys.
            """
            with self._lock:
                rows = self._db.execute(
                    "SELECT key FROM workflow_schedule_state WHERE paused = 1"
                ).fetchall()
            return frozenset(row["key"] for row in rows)

        return await asyncio.to_thread(work)

    async def admit_flow(
        self,
        run: RunRecord,
        root_step: StepRecord,
        events: tuple[tuple[HistoryEventType, dict[str, Any]], ...],
        gate: FlowGate,
        now: float,
    ) -> FlowAdmission:
        """Admit a run under a start policy, atomically.

        ``BEGIN IMMEDIATE`` takes the database write lock up front, so the
        whole decision is atomic against every other connection -- including
        one held by a different process sharing the file, which is exactly
        where an in-process lock stops helping.

        Args:
            run: The run record to create, carrying the flow key.
            root_step: The preallocated root mailbox slot.
            events: History events to append on creation.
            gate: The policy to enforce.
            now: Current time in epoch seconds.

        Returns:
            What was done, decided inside the transaction.
        """

        def work() -> FlowAdmission:
            """Run the whole gated admission in one write transaction.

            Returns:
                The admission outcome.
            """
            terminal = tuple(s.value for s in TERMINAL_RUN_STATUSES)
            not_terminal = f"status NOT IN ({','.join('?' * len(terminal))})"
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
                            return FlowAdmission("deduplicated", row["run_id"])
                    active = self._db.execute(
                        "SELECT run_id FROM workflow_runs"
                        f" WHERE workflow_id = ? AND flow_key = ? AND {not_terminal}"
                        " ORDER BY created_at, run_id",
                        (run.workflow_id, run.flow_key, *terminal),
                    ).fetchall()
                    if gate.singleton_skip and active:
                        self._db.execute("ROLLBACK")
                        return FlowAdmission("skipped", active[0]["run_id"])
                    cancelled: list[str] = []
                    if gate.singleton_cancel:
                        for row in active:
                            self._db.execute(
                                "UPDATE workflow_runs SET cancel_requested = 1,"
                                " status = ?, updated_at = ? WHERE run_id = ?",
                                (RunStatus.CANCELLING.value, now, row["run_id"]),
                            )
                            self._append_events(
                                row["run_id"],
                                ((HistoryEventType.RUN_CANCEL_REQUESTED, {}),),
                                now,
                            )
                            cancelled.append(row["run_id"])
                    due_at = root_step.due_at
                    if gate.rate_limit is not None:
                        limit, window = gate.rate_limit
                        started = self._db.execute(
                            "SELECT count(*) AS n FROM workflow_runs"
                            " WHERE workflow_id = ? AND flow_key = ?"
                            " AND created_at > ?",
                            (run.workflow_id, run.flow_key, now - window),
                        ).fetchone()["n"]
                        if started >= limit:
                            self._db.execute("ROLLBACK")
                            return FlowAdmission("rejected", retry_after=window)
                    if gate.throttle is not None:
                        limit, window = gate.throttle
                        row = self._db.execute(
                            "SELECT MAX(s.due_at, r.created_at) AS start"
                            " FROM workflow_runs r JOIN workflow_steps s"
                            " ON s.run_id = r.run_id AND s.ordinal = 0"
                            " WHERE r.workflow_id = ? AND r.flow_key = ?"
                            " ORDER BY start DESC LIMIT 1 OFFSET ?",
                            (run.workflow_id, run.flow_key, limit - 1),
                        ).fetchone()
                        if row is not None and row["start"] + window > now:
                            due_at = row["start"] + window
                    if gate.debounce is not None:
                        if active:
                            deferred = self._db.execute(
                                "UPDATE workflow_steps SET args = ?, due_at = ?,"
                                " updated_at = ? WHERE run_id = ? AND ordinal = 0"
                                " AND status = ?",
                                (
                                    json.dumps(root_step.args),
                                    now + gate.debounce,
                                    now,
                                    active[0]["run_id"],
                                    StepStatus.READY.value,
                                ),
                            )
                            if deferred.rowcount:
                                self._db.execute("COMMIT")
                                return FlowAdmission("coalesced", active[0]["run_id"])
                        due_at = now + gate.debounce
                    if run.request_key is not None:
                        self._db.execute(
                            "INSERT INTO workflow_dedupe"
                            " (workflow_id, request_key, run_id) VALUES (?, ?, ?)",
                            (run.workflow_id, run.request_key, run.run_id),
                        )
                    self._insert_run(run)
                    self._insert_step(dataclasses.replace(root_step, due_at=due_at))
                    self._append_events(run.run_id, events, run.created_at)
                    if run.request_key is not None:
                        # Policy admission is still admission: early mail
                        # flushes on this door exactly as on the plain one.
                        self._flush_parked_in_txn(
                            run.workflow_id,
                            run.request_key,
                            run.run_id,
                            run.created_at,
                        )
                    self._db.execute("COMMIT")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise
                return FlowAdmission("started", run.run_id, cancelled=tuple(cancelled))

        return await asyncio.to_thread(work)

    async def purge_runs(
        self,
        before: float,
        *,
        workflow_id: str | None = None,
        attribution: Mapping[str, str] | None = None,
    ) -> int:
        """Delete terminal runs not updated since a cutoff, and all their data.

        Args:
            before: Delete runs whose last update is older than this.
            workflow_id: Restrict to one workflow identity.
            attribution: Who asked and why, recorded in the audit log.

        Returns:
            How many runs were deleted.
        """

        def work() -> int:
            """Delete in one transaction on the worker thread.

            Returns:
                How many runs were deleted.
            """
            terminal = tuple(s.value for s in TERMINAL_RUN_STATUSES)
            where = f"status IN ({','.join('?' * len(terminal))}) AND updated_at < ?"
            params: tuple[Any, ...] = (*terminal, before)
            if workflow_id is not None:
                where += " AND workflow_id = ?"
                params = (*params, workflow_id)
            with self._lock:
                self._db.execute("BEGIN IMMEDIATE")
                try:
                    doomed = [
                        row["run_id"]
                        for row in self._db.execute(
                            f"SELECT run_id FROM workflow_runs WHERE {where}",
                            params,
                        ).fetchall()
                    ]
                    for run_id in doomed:
                        for table in (
                            "workflow_steps",
                            "workflow_history",
                            "workflow_inbox",
                            "workflow_substeps",
                        ):
                            self._db.execute(
                                f"DELETE FROM {table} WHERE run_id = ?", (run_id,)
                            )
                        self._db.execute(
                            "DELETE FROM workflow_dedupe WHERE run_id = ?", (run_id,)
                        )
                        self._db.execute(
                            "DELETE FROM workflow_runs WHERE run_id = ?", (run_id,)
                        )
                    self._audit_sql(
                        attribution,
                        "purge_runs",
                        workflow_id or "*",
                        {"before": before, "deleted": len(doomed)},
                        before,
                    )
                    self._db.execute("COMMIT")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise
                return len(doomed)

        return await asyncio.to_thread(work)

    async def epoch_time(self) -> float | None:
        """This store never leaves one host, whose clock is the authority.

        Returns:
            None: the process clock is correct here.
        """
        return None

    async def claim_next(
        self,
        now: float,
        *,
        lease_duration: float = DEFAULT_LEASE_DURATION,
        queues: tuple[str, ...] | None = None,
        release: str | None = None,
    ) -> Claim | None:
        """Claim the due frontier step of some runnable run.

        Args:
            now: Current time in epoch seconds.
            lease_duration: Seconds of renewal silence tolerated before the
                claim is treated as orphaned.
            queues: Queues this worker serves; None serves every queue. A run
                whose frontier sits on an unserved queue is skipped whole,
                because claiming a later slot would break its ordering.
            release: The claiming worker's release identity. A run pinned to
                a different release is skipped: it drains on the release that
                admitted it, so one run never mixes two releases' code.

        Returns:
            A fenced claim, or None when nothing is claimable right now.
        """

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
            """
            with self._lock:
                self._db.execute("BEGIN IMMEDIATE")
                claim = None
                try:
                    # Due-ness filters first, through the wake index, so a
                    # store full of sleeping runs answers from the index
                    # instead of loading every run and its steps into Python;
                    # only due candidates pay the frontier check, and LIMIT
                    # stops the scan at the first winner.
                    sql, params = _sqlite_frontier_query(
                        "s.*",
                        now,
                        queues,
                        due_only=True,
                        order="s.due_at, s.run_id",
                        limit=1,
                        release=release,
                    )
                    row = self._db.execute(sql, params).fetchone()
                    if row is not None:
                        frontier = _step_from_row(row)
                        run_row = self._db.execute(
                            "SELECT * FROM workflow_runs WHERE run_id = ?",
                            (frontier.run_id,),
                        ).fetchone()
                        run = _run_from_row(run_row)
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
                    self._db.execute("COMMIT" if claim is not None else "ROLLBACK")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise
                return claim

        return await asyncio.to_thread(work)

    def _check_claim(self, claim: Claim) -> float | None:
        """Validate that a claim still owns its step and state version.

        Args:
            claim: The claim to validate.

        Returns:
            The run's deadline, when it has one.

        Raises:
            StaleClaimError: If the claim was fenced.
        """
        row = self._db.execute(
            "SELECT s.status AS step_status, s.epoch AS epoch,"
            " r.state_version AS state_version, r.deadline AS deadline"
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
        return row["deadline"]

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

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
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

        return await asyncio.to_thread(work)

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

        def work() -> None:
            """Run the operation on the worker thread."""
            with self._lock:
                self._db.execute("BEGIN IMMEDIATE")
                try:
                    deadline = self._check_claim(claim)
                    # Past the deadline the only permitted outcome is
                    # TIMED_OUT, and that is the sweep's, not this one's.
                    _fence_deadline(claim.run.run_id, deadline, now)
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
                        self._append_events(
                            child_run.run_id,
                            _child_admission_events(child_run, child_step),
                            now,
                        )
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
                    if completion.run_status in TERMINAL_RUN_STATUSES:
                        self._close_children_sql(claim.run.run_id, now)
                    if completion.parent_arrival is not None:
                        self._apply_arrival_sql(*completion.parent_arrival, now)
                    self._db.execute("COMMIT")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise

        await asyncio.to_thread(work)

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

        def work() -> None:
            """Run the operation on the worker thread."""
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

        await asyncio.to_thread(work)

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

        def work() -> None:
            """Run the operation on the worker thread."""
            with self._lock:
                self._db.execute("BEGIN IMMEDIATE")
                try:
                    self._append_events(run_id, events, now)
                    self._db.execute("COMMIT")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise

        await asyncio.to_thread(work)

    async def deliver(
        self,
        run_id: str,
        wait_key: str,
        dedupe_key: str,
        payload: Any,
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

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
            """
            with self._lock:
                self._db.execute("BEGIN IMMEDIATE")
                try:
                    disposition = self._deliver_in_txn(
                        run_id, wait_key, dedupe_key, payload, now
                    )
                    self._db.execute("COMMIT")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise
                return disposition

        return await asyncio.to_thread(work)

    def _deliver_in_txn(
        self,
        run_id: str,
        wait_key: str,
        dedupe_key: str,
        payload: Any,
        now: float,
    ) -> DeliveryDisposition:
        """Deliver inside the caller's open transaction.

        Refusal branches write nothing, so the caller's transaction stays
        committable whatever this returns -- which is what lets admission
        flush parked deliveries in its own transaction.

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
        row = self._db.execute(
            "SELECT status, deadline FROM workflow_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return "unknown_run"
        if row["status"] in terminal:
            return "run_terminal"
        if row["deadline"] is not None and row["deadline"] <= now:
            # A past-deadline run can never execute the continuation; saying
            # "resolved" would be a lie.
            return "expired"
        seen = self._db.execute(
            "SELECT 1 FROM workflow_inbox"
            " WHERE run_id = ? AND wait_key = ? AND dedupe_key = ?",
            (run_id, wait_key, dedupe_key),
        ).fetchone()
        if seen is not None:
            self._append_events(
                run_id,
                ((HistoryEventType.SIGNAL_DUPLICATE, {"wait_key": wait_key}),),
                now,
            )
            return "duplicate"
        frontier = _frontier(self._load_steps(run_id))
        if frontier is not None and _wait_expired(frontier, now):
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

        def work() -> None:
            """Run the operation on the worker thread."""
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

        await asyncio.to_thread(work)

    def _apply_arrival_sql(
        self,
        run_id: str,
        ordinal: int,
        payload: dict[str, Any],
        dedupe_key: str,
        now: float,
    ) -> str:
        """Count one arrival inside the caller's open transaction.

        Args:
            run_id: The waiting parent run.
            ordinal: The join slot's ordinal.
            payload: The arriving result.
            dedupe_key: Identity of the arrival.
            now: Current time in epoch seconds.

        Returns:
            What the store did with the arrival.
        """
        terminal = tuple(status.value for status in TERMINAL_RUN_STATUSES)
        wait_key = f"join:{ordinal}"
        run_row = self._db.execute(
            "SELECT status, deadline FROM workflow_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if run_row is None:
            return "unknown_run"
        if run_row["status"] in terminal:
            return "run_terminal"
        if run_row["deadline"] is not None and run_row["deadline"] <= now:
            # The join can never run its continuation: the sweep is about to
            # finalize this parent TIMED_OUT and tombstone the slot.
            return "expired"
        seen = self._db.execute(
            "SELECT 1 FROM workflow_inbox"
            " WHERE run_id = ? AND wait_key = ? AND dedupe_key = ?",
            (run_id, wait_key, dedupe_key),
        ).fetchone()
        if seen is not None:
            return "duplicate"
        step_row = self._db.execute(
            "SELECT * FROM workflow_steps WHERE run_id = ? AND ordinal = ?",
            (run_id, ordinal),
        ).fetchone()
        if step_row is None or step_row["status"] != StepStatus.BLOCKED.value:
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
        return "resolved" if done else "counted"

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

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
            """
            terminal = tuple(s.value for s in TERMINAL_RUN_STATUSES)
            wait_key = f"join:{ordinal}"
            with self._lock:
                self._db.execute("BEGIN IMMEDIATE")
                try:
                    run_row = self._db.execute(
                        "SELECT status, deadline FROM workflow_runs WHERE run_id = ?",
                        (run_id,),
                    ).fetchone()
                    if run_row is None:
                        self._db.execute("ROLLBACK")
                        return "unknown_run"
                    if run_row["status"] in terminal:
                        self._db.execute("ROLLBACK")
                        return "run_terminal"
                    if run_row["deadline"] is not None and run_row["deadline"] <= now:
                        # The join can never run its continuation: the sweep
                        # is about to finalize this parent TIMED_OUT.
                        self._db.execute("ROLLBACK")
                        return "expired"
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
                    if (
                        step_row is None
                        or step_row["status"] != StepStatus.BLOCKED.value
                    ):
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
                            StepStatus.READY.value
                            if done
                            else StepStatus.BLOCKED.value,
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

        return await asyncio.to_thread(work)

    async def count_active(self, workflow_id: str, flow_key: str) -> int:
        """Count runs of a root still in flight under a flow-control key.

        Args:
            workflow_id: The workflow identity.
            flow_key: The computed grouping key.

        Returns:
            How many non-terminal runs share the key.
        """

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
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

        return await asyncio.to_thread(work)

    async def first_active(self, workflow_id: str, flow_key: str) -> RunRecord | None:
        """Find the oldest run still in flight under a flow-control key.

        Args:
            workflow_id: The workflow identity.
            flow_key: The computed grouping key.

        Returns:
            The run, or None when the key has no active run.
        """

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
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

        return await asyncio.to_thread(work)

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

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
            """
            with self._lock:
                row = self._db.execute(
                    "SELECT COUNT(*) AS n FROM workflow_runs"
                    " WHERE workflow_id = ? AND flow_key = ? AND created_at > ?",
                    (workflow_id, flow_key, since),
                ).fetchone()
                return row["n"]

        return await asyncio.to_thread(work)

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

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
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

        return await asyncio.to_thread(work)

    async def defer_root(self, run_id: str, due_at: float, now: float) -> bool:
        """Push a not-yet-started run's root slot later, for debouncing.

        Args:
            run_id: The pending run.
            due_at: The new earliest start time.
            now: Current time in epoch seconds.

        Returns:
            True when the root had not started and was deferred.
        """

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
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

        return await asyncio.to_thread(work)

    async def request_cancel(
        self,
        run_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Record cancellation intent on a run.

        Args:
            run_id: The run to cancel.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".

        Returns:
            True if intent was recorded on a nonterminal run.
        """

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
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
                        run_id,
                        (
                            (
                                HistoryEventType.RUN_CANCEL_REQUESTED,
                                dict(attribution or {}),
                            ),
                        ),
                        now,
                    )
                    self._db.execute("COMMIT")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise
                return True

        return await asyncio.to_thread(work)

    async def control_pending(self, now: float) -> tuple[RunRecord, ...]:
        """List drained runs awaiting a control transition.

        Args:
            now: Current time in epoch seconds.

        Returns:
            The runs awaiting finalization.
        """

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
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

        return await asyncio.to_thread(work)

    async def finalize_run(
        self,
        run_id: str,
        *,
        status: RunStatus,
        error: dict[str, Any] | None,
        event: HistoryEventType,
        now: float,
        result: Any = None,
        parent_arrival: tuple[str, int, dict[str, Any], str] | None = None,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Terminate a drained run and tombstone its unresolved slots.

        Args:
            run_id: The run to finalize.
            status: The terminal status to record.
            error: Error payload recorded on the run.
            event: The terminal history event type.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".
            result: Result to record, for an operator forcing completion.
            parent_arrival: When this run is a child, the arrival to deliver
                to its parent's join, applied in this same transaction.

        Returns:
            True if the run was finalized.
        """

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
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
                        "UPDATE workflow_runs SET status = ?, error = ?,"
                        " result = COALESCE(?, result), updated_at = ?"
                        " WHERE run_id = ?",
                        (status.value, _dump(error), _dump(result), now, run_id),
                    )
                    events: list[tuple[HistoryEventType, dict[str, Any]]] = [
                        (HistoryEventType.STEP_TOMBSTONED, {"ordinal": row["ordinal"]})
                        for row in open_rows
                    ]
                    events.append((
                        event,
                        {
                            **({} if error is None else dict(error)),
                            **(attribution or {}),
                        },
                    ))
                    self._append_events(run_id, events, now)
                    self._close_children_sql(run_id, now)
                    if parent_arrival is not None:
                        self._apply_arrival_sql(*parent_arrival, now)
                    self._db.execute("COMMIT")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise
                return True

        return await asyncio.to_thread(work)

    async def skip_step(
        self,
        run_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Give up on a stuck step and let the run carry on past it.

        The operator's answer to a step that cannot succeed and is not worth
        failing the run over -- a vendor that retired an endpoint, a
        notification nobody needs any more. The step is marked SKIPPED, which
        is terminal and recorded as a decision rather than an outcome, and the
        run continues at whatever comes next. Legal only on a run stopped for
        attention or failure, so it can never race a working attempt.

        Args:
            run_id: The run to unstick.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".

        Returns:
            True if a blocking step was skipped.
        """

        def work() -> bool:
            """Skip the blocking step on the worker thread.

            Returns:
                Whether a blocking step was skipped.
            """
            with self._lock:
                self._db.execute("BEGIN IMMEDIATE")
                try:
                    row = self._db.execute(
                        "SELECT s.ordinal AS ordinal FROM workflow_steps s"
                        " JOIN workflow_runs r ON r.run_id = s.run_id"
                        " WHERE s.run_id = ? AND s.status IN (?, ?, ?)"
                        " AND r.status IN (?, ?) ORDER BY s.ordinal LIMIT 1",
                        (
                            run_id,
                            StepStatus.FAILED.value,
                            StepStatus.TIMED_OUT.value,
                            StepStatus.NEEDS_ATTENTION.value,
                            RunStatus.NEEDS_ATTENTION.value,
                            RunStatus.FAILED.value,
                        ),
                    ).fetchone()
                    if row is None:
                        self._db.execute("ROLLBACK")
                        return False
                    self._db.execute(
                        "UPDATE workflow_steps SET status = ?, lease_expires_at = 0,"
                        " updated_at = ? WHERE run_id = ? AND ordinal = ?",
                        (StepStatus.SKIPPED.value, now, run_id, row["ordinal"]),
                    )
                    restored = [
                        r["ordinal"]
                        for r in self._db.execute(
                            "SELECT ordinal FROM workflow_steps WHERE run_id = ?"
                            " AND status = ? ORDER BY ordinal",
                            (run_id, StepStatus.CANCELLED.value),
                        ).fetchall()
                    ]
                    if restored:
                        # The stopping failure tombstoned these; continuing
                        # "from there" is a lie unless they come back. Nothing
                        # independently cancelled can be in a run these
                        # actions accept (see MemoryRunStore._restore_tombstoned).
                        # Waits and joins come back BLOCKED with their
                        # arrival counts and deadlines intact, never READY --
                        # restored-as-READY they would run immediately with a
                        # missing or partial payload. Plain slots keep their
                        # own due_at, so a restored delay still waits.
                        self._db.execute(
                            "UPDATE workflow_steps SET status = CASE WHEN"
                            " wait_key IS NULL THEN ? ELSE ? END, attempts = 0,"
                            " lease_expires_at = 0, error = NULL,"
                            " updated_at = ? WHERE run_id = ? AND status = ?",
                            (
                                StepStatus.READY.value,
                                StepStatus.BLOCKED.value,
                                now,
                                run_id,
                                StepStatus.CANCELLED.value,
                            ),
                        )
                    terminal = tuple(s.value for s in TERMINAL_STEP_STATUSES)
                    open_left = self._db.execute(
                        "SELECT 1 FROM workflow_steps WHERE run_id = ?"
                        f" AND status NOT IN ({','.join('?' * len(terminal))})"
                        " LIMIT 1",
                        (run_id, *terminal),
                    ).fetchone()
                    self._db.execute(
                        "UPDATE workflow_runs SET status = ?, error = NULL,"
                        " updated_at = ? WHERE run_id = ?",
                        (
                            RunStatus.PENDING.value
                            if open_left
                            else RunStatus.COMPLETED.value,
                            now,
                            run_id,
                        ),
                    )
                    events = [
                        (
                            HistoryEventType.STEP_SKIPPED,
                            {"ordinal": row["ordinal"], **(attribution or {})},
                        ),
                        *(
                            (HistoryEventType.STEP_RESTORED, {"ordinal": ordinal})
                            for ordinal in restored
                        ),
                    ]
                    if not open_left:
                        events.append((HistoryEventType.RUN_COMPLETED, {}))
                    self._append_events(run_id, events, now)
                    if not open_left:
                        # Completed by an operator's decision is still
                        # completed: branches are told to stop, and a parent
                        # joined on this run hears it finished instead of
                        # waiting forever.
                        self._close_children_sql(run_id, now)
                        parent = self._db.execute(
                            "SELECT parent_run_id, parent_ordinal FROM"
                            " workflow_runs WHERE run_id = ?",
                            (run_id,),
                        ).fetchone()
                        if parent is not None and (parent["parent_run_id"] is not None):
                            self._apply_arrival_sql(
                                parent["parent_run_id"],
                                parent["parent_ordinal"],
                                {
                                    "run_id": run_id,
                                    "status": RunStatus.COMPLETED.value,
                                    "result": None,
                                    "error": None,
                                },
                                run_id,
                                now,
                            )
                    self._db.execute("COMMIT")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise
                return True

        return await asyncio.to_thread(work)

    async def retry_run(
        self,
        run_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Re-open a failed run at the step that failed.

        The operator's answer to a run that failed for a reason now fixed: the
        failed step runs again with a fresh attempt budget, and the failure
        stays in history rather than being erased.

        Args:
            run_id: The run to retry.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".

        Returns:
            True if a failed run was re-opened.
        """

        def work() -> bool:
            """Re-open the failed step on the worker thread.

            Returns:
                Whether a failed run was re-opened.
            """
            with self._lock:
                self._db.execute("BEGIN IMMEDIATE")
                try:
                    row = self._db.execute(
                        "SELECT ordinal FROM workflow_steps WHERE run_id = ?"
                        " AND status IN (?, ?) ORDER BY ordinal LIMIT 1",
                        (run_id, StepStatus.FAILED.value, StepStatus.TIMED_OUT.value),
                    ).fetchone()
                    cursor = self._db.execute(
                        "UPDATE workflow_runs SET status = ?, error = NULL,"
                        " updated_at = ? WHERE run_id = ? AND status = ?",
                        (RunStatus.PENDING.value, now, run_id, RunStatus.FAILED.value),
                    )
                    if row is None or cursor.rowcount == 0:
                        self._db.execute("ROLLBACK")
                        return False
                    self._db.execute(
                        "UPDATE workflow_steps SET status = ?, attempts = 0,"
                        " due_at = ?, lease_expires_at = 0, error = NULL,"
                        " updated_at = ? WHERE run_id = ? AND ordinal = ?",
                        (StepStatus.READY.value, now, now, run_id, row["ordinal"]),
                    )
                    restored = [
                        r["ordinal"]
                        for r in self._db.execute(
                            "SELECT ordinal FROM workflow_steps WHERE run_id = ?"
                            " AND status = ? ORDER BY ordinal",
                            (run_id, StepStatus.CANCELLED.value),
                        ).fetchall()
                    ]
                    if restored:
                        # The stopping failure tombstoned these; continuing
                        # "from there" is a lie unless they come back. Nothing
                        # independently cancelled can be in a run these
                        # actions accept (see MemoryRunStore._restore_tombstoned).
                        # Waits and joins come back BLOCKED with their
                        # arrival counts and deadlines intact, never READY --
                        # restored-as-READY they would run immediately with a
                        # missing or partial payload. Plain slots keep their
                        # own due_at, so a restored delay still waits.
                        self._db.execute(
                            "UPDATE workflow_steps SET status = CASE WHEN"
                            " wait_key IS NULL THEN ? ELSE ? END, attempts = 0,"
                            " lease_expires_at = 0, error = NULL,"
                            " updated_at = ? WHERE run_id = ? AND status = ?",
                            (
                                StepStatus.READY.value,
                                StepStatus.BLOCKED.value,
                                now,
                                run_id,
                                StepStatus.CANCELLED.value,
                            ),
                        )
                    self._append_events(
                        run_id,
                        (
                            (
                                HistoryEventType.RUN_RESUMED,
                                {"origin": "retry", **(attribution or {})},
                            ),
                            *(
                                (HistoryEventType.STEP_RESTORED, {"ordinal": ordinal})
                                for ordinal in restored
                            ),
                        ),
                        now,
                    )
                    self._db.execute("COMMIT")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise
                return True

        return await asyncio.to_thread(work)

    async def resume_run(
        self,
        run_id: str,
        now: float,
        attribution: Mapping[str, str] | None = None,
    ) -> bool:
        """Re-open a suspended run so its frontier step runs again.

        Args:
            run_id: The run to resume.
            now: Current time in epoch seconds.
            attribution: Who asked and why, e.g. ``{"actor": ..., "reason":
                ...}``, merged into the operator-facing history event so the
                run's own story answers "who did this".

        Returns:
            True if a suspended run was re-opened.
        """

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
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
                    self._append_events(
                        run_id,
                        ((HistoryEventType.RUN_RESUMED, dict(attribution or {})),),
                        now,
                    )
                    self._db.execute("COMMIT")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise
                return True

        return await asyncio.to_thread(work)

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

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
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
                            # Exhaustion is a failure, and failure closes the
                            # run completely: open slots tombstoned, branches
                            # told to stop.
                            step_terminal = tuple(
                                s.value for s in TERMINAL_STEP_STATUSES
                            )
                            open_rows = self._db.execute(
                                "SELECT ordinal FROM workflow_steps"
                                " WHERE run_id = ? AND ordinal != ? AND status"
                                " NOT IN"
                                f" ({','.join('?' * len(step_terminal))})",
                                (step.run_id, step.ordinal, *step_terminal),
                            ).fetchall()
                            for open_row in open_rows:
                                self._db.execute(
                                    "UPDATE workflow_steps SET status = ?,"
                                    " updated_at = ? WHERE run_id = ?"
                                    " AND ordinal = ?",
                                    (
                                        StepStatus.CANCELLED.value,
                                        now,
                                        step.run_id,
                                        open_row["ordinal"],
                                    ),
                                )
                            self._append_events(
                                step.run_id,
                                tuple(
                                    (
                                        HistoryEventType.STEP_TOMBSTONED,
                                        {"ordinal": open_row["ordinal"]},
                                    )
                                    for open_row in open_rows
                                ),
                                now,
                            )
                            self._close_children_sql(step.run_id, now)
                            failed.append(step.run_id)
                            parent = self._db.execute(
                                "SELECT parent_run_id, parent_ordinal FROM"
                                " workflow_runs WHERE run_id = ?",
                                (step.run_id,),
                            ).fetchone()
                            if parent is not None and (
                                parent["parent_run_id"] is not None
                            ):
                                self._apply_arrival_sql(
                                    parent["parent_run_id"],
                                    parent["parent_ordinal"],
                                    {
                                        "run_id": step.run_id,
                                        "status": RunStatus.FAILED.value,
                                        "result": None,
                                        "error": {
                                            "reason": "recovery_budget_exhausted"
                                        },
                                    },
                                    step.run_id,
                                    now,
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
                return recovered, tuple(failed)

        return await asyncio.to_thread(work)

    async def list_runs(self, query: RunQuery) -> tuple[RunRecord, ...]:
        """List runs matching a query, newest first.

        Args:
            query: The filters and pagination cursor to apply.

        Returns:
            The matching run records.
        """

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
            """
            where, params = _sqlite_run_filters(query)
            with self._lock:
                rows = self._db.execute(
                    f"SELECT * FROM workflow_runs{where}"
                    " ORDER BY created_at DESC, run_id DESC LIMIT ?",
                    (*params, query.limit),
                ).fetchall()
                return tuple(_run_from_row(row) for row in rows)

        return await asyncio.to_thread(work)

    async def count_runs(self, query: RunQuery) -> int:
        """Count runs matching a query.

        The count ignores ``limit`` and ``created_before``: those page a
        listing, and an aggregate is not a page. Everything else filters as
        it does for ``list_runs``, so a count and a listing always describe
        the same set.

        Args:
            query: The filters to apply.

        Returns:
            How many runs match.
        """

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
            """
            where, params = _sqlite_run_filters(
                dataclasses.replace(query, created_before=None)
            )
            with self._lock:
                row = self._db.execute(
                    f"SELECT count(*) AS n FROM workflow_runs{where}", params
                ).fetchone()
                return int(row["n"])

        return await asyncio.to_thread(work)

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

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
            """
            with self._lock:
                rows = self._db.execute(
                    "SELECT * FROM workflow_runs WHERE parent_run_id = ?"
                    " AND parent_ordinal = ? ORDER BY created_at, run_id",
                    (parent_run_id, parent_ordinal),
                ).fetchall()
                return tuple(_run_from_row(row) for row in rows)

        return await asyncio.to_thread(work)

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

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
            """
            with self._lock:
                row = self._db.execute(
                    "SELECT run_id FROM workflow_dedupe"
                    " WHERE workflow_id = ? AND request_key = ?",
                    (workflow_id, request_key),
                ).fetchone()
                return None if row is None else row["run_id"]

        return await asyncio.to_thread(work)

    async def get_run(self, run_id: str) -> RunRecord | None:
        """Load one run record.

        Args:
            run_id: The run identity.

        Returns:
            The record, or None if unknown.
        """

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
            """
            with self._lock:
                row = self._db.execute(
                    "SELECT * FROM workflow_runs WHERE run_id = ?", (run_id,)
                ).fetchone()
                return None if row is None else _run_from_row(row)

        return await asyncio.to_thread(work)

    async def get_steps(self, run_id: str) -> tuple[StepRecord, ...]:
        """Load a run's mailbox slots in ordinal order.

        Args:
            run_id: The run identity.

        Returns:
            The step records.
        """

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
            """
            with self._lock:
                return tuple(self._load_steps(run_id))

        return await asyncio.to_thread(work)

    async def record_substep(
        self, run_id: str, ordinal: int, epoch: int, key: str, payload: Any, now: float
    ) -> bool:
        """Durably record one substep result inside a claimed attempt.

        The write is fenced on the step's claim epoch: an attempt whose lease
        was reclaimed must not pollute the journal a newer attempt is reading.
        The first write for a key wins, so a duplicate is a no-op that still
        reports success -- memoization reads before it writes, so a duplicate
        only means two racing writers agreed.

        Args:
            run_id: The owning run.
            ordinal: The mailbox slot being executed.
            epoch: The claim fence of the writing attempt.
            key: The substep's memoization key, unique within the step.
            payload: JSON-compatible result to record.
            now: Current time in epoch seconds.

        Returns:
            True when recorded (or already recorded); False when the writer
            was fenced and must stop.
        """

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
            """
            with self._lock:
                self._db.execute("BEGIN IMMEDIATE")
                try:
                    row = self._db.execute(
                        "SELECT status, epoch FROM workflow_steps"
                        " WHERE run_id = ? AND ordinal = ?",
                        (run_id, ordinal),
                    ).fetchone()
                    if (
                        row is None
                        or row["status"] != StepStatus.CLAIMED.value
                        or row["epoch"] != epoch
                    ):
                        self._db.execute("ROLLBACK")
                        return False
                    cursor = self._db.execute(
                        "INSERT OR IGNORE INTO workflow_substeps"
                        " (run_id, ordinal, key, payload, created_at)"
                        " VALUES (?, ?, ?, ?, ?)",
                        (run_id, ordinal, key, json.dumps(payload), now),
                    )
                    if cursor.rowcount:
                        self._append_events(
                            run_id,
                            (
                                (
                                    HistoryEventType.SUBSTEP_RECORDED,
                                    {"ordinal": ordinal, "key": key},
                                ),
                            ),
                            now,
                        )
                    self._db.execute("COMMIT")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise
                return True

        return await asyncio.to_thread(work)

    async def get_substeps(self, run_id: str, ordinal: int) -> dict[str, Any]:
        """Load the recorded substep results of one step.

        Args:
            run_id: The owning run.
            ordinal: The mailbox slot.

        Returns:
            Recorded payloads by key, in recording order.
        """

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
            """
            with self._lock:
                rows = self._db.execute(
                    "SELECT key, payload FROM workflow_substeps"
                    " WHERE run_id = ? AND ordinal = ? ORDER BY created_at, key",
                    (run_id, ordinal),
                ).fetchall()
                return {row["key"]: json.loads(row["payload"]) for row in rows}

        return await asyncio.to_thread(work)

    async def get_history(self, run_id: str) -> tuple[HistoryEvent, ...]:
        """Load a run's append-only history in sequence order.

        Args:
            run_id: The run identity.

        Returns:
            The history events.
        """

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
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

        return await asyncio.to_thread(work)

    async def read_schedule_cursor(self, key: str) -> float | None:
        """Read where a schedule's catch-up last reached.

        Args:
            key: The schedule identity, "{workflow_id}:{handler_id}".

        Returns:
            The last swept time, or None when the schedule is new here.
        """

        def work() -> float | None:
            """Read the cursor on the worker thread.

            Returns:
                The stored time, or None.
            """
            with self._lock:
                row = self._db.execute(
                    "SELECT at FROM workflow_schedules WHERE key = ?", (key,)
                ).fetchone()
                return None if row is None else row["at"]

        return await asyncio.to_thread(work)

    async def write_schedule_cursor(self, key: str, at: float) -> None:
        """Record where a schedule's catch-up has now reached.

        Persisting this is what makes a restart resume rather than silently
        skip: an in-memory cursor reseeded at startup treats every occurrence
        during the downtime as if it had already fired.

        Args:
            key: The schedule identity, "{workflow_id}:{handler_id}".
            at: The time swept up to, in epoch seconds.
        """

        def work() -> None:
            """Write the cursor on the worker thread."""
            with self._lock:
                self._db.execute("BEGIN IMMEDIATE")
                try:
                    self._db.execute(
                        "INSERT INTO workflow_schedules (key, at) VALUES (?, ?)"
                        " ON CONFLICT(key) DO UPDATE SET"
                        " at = MAX(at, excluded.at)",
                        (key, at),
                    )
                    self._db.execute("COMMIT")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise

        await asyncio.to_thread(work)

    async def next_due(
        self, now: float, *, queues: tuple[str, ...] | None = None
    ) -> float | None:
        """Earliest future time any runnable run becomes claimable.

        Args:
            now: Current time in epoch seconds.
            queues: Queues this worker serves; None serves every queue.

        Returns:
            The epoch time, or None when no future work is scheduled.
        """

        def work():
            """Run the operation on the worker thread.

            Returns:
                The operation's result.
            """
            with self._lock:
                # Wake times are due_at in every waking status, so the first
                # row of a due_at-ordered index walk that survives the
                # frontier check is the minimum -- no per-run Python loop.
                sql, params = _sqlite_frontier_query(
                    "s.due_at AS wake",
                    now,
                    queues,
                    due_only=False,
                    order="s.due_at",
                    limit=1,
                )
                row = self._db.execute(sql, params).fetchone()
                return None if row is None else row["wake"]

        return await asyncio.to_thread(work)
