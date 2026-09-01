"""Deterministic test harness for workflow definitions.

The harness runs registered workflows on an in-memory store with a virtual
clock, so tests drive retries, durable delays, and deadlines by advancing time
instead of sleeping. Retry jitter is disabled for determinism.

Lease renewal runs on a real-time cadence while lease expiry is measured on the
virtual clock, so an attempt held across ``advance()`` is renewed by the next
pump rather than expiring; ``lease_duration`` is virtual seconds and
``lease_renew_interval`` is real seconds.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from reflex_base.workflow import (
    DEFAULT_LEASE_DURATION,
    DEFAULT_MAX_RECOVERIES,
    parse_duration,
)

from reflex.workflow.kernel import WorkflowObserver
from reflex.workflow.records import TERMINAL_RUN_STATUSES, RunStatus
from reflex.workflow.runtime import WorkflowRuntime, _context_runtime
from reflex.workflow.store import MemoryRunStore

if TYPE_CHECKING:
    from collections.abc import Mapping

    from reflex_base.workflow import DurationLike

    from reflex.state import BaseState
    from reflex.workflow.kernel import WorkflowKernel
    from reflex.workflow.records import (
        HistoryEvent,
        RunRecord,
        RunSnapshot,
        StartResult,
    )
    from reflex.workflow.store import RunStore

DEFAULT_START_TIME = 1_000_000.0


class _VirtualClock:
    """A manually advanced epoch-seconds clock."""

    def __init__(self, now: float):
        """Initialize the clock.

        Args:
            now: The starting time in epoch seconds.
        """
        self.now = now

    def __call__(self) -> float:
        """Read the clock.

        Returns:
            The current virtual time in epoch seconds.
        """
        return self.now


class WorkflowTestHarness:
    """Runs workflows deterministically for tests.

    Usage::

        async with WorkflowTestHarness(MyWorkflow) as harness:
            result = await harness.start(MyWorkflow.begin(payload))
            await harness.advance("5s")
            snapshot = await harness.get_run(result.run_id)
    """

    def __init__(
        self,
        *workflow_classes: type[BaseState],
        store: RunStore | None = None,
        start_time: float = DEFAULT_START_TIME,
        lease_duration: DurationLike = DEFAULT_LEASE_DURATION,
        lease_renew_interval: float | None = None,
        observer: WorkflowObserver | None = None,
        max_recoveries: int = DEFAULT_MAX_RECOVERIES,
        max_concurrency: int = 1,
    ):
        """Initialize the harness.

        Args:
            workflow_classes: Workflow classes to register.
            store: Run store override; defaults to a fresh in-memory store.
            start_time: Initial virtual time in epoch seconds.
            lease_duration: Virtual seconds a claim survives without renewal.
            lease_renew_interval: Real seconds between lease renewals.
            observer: Receives every recorded run transition.
            max_recoveries: Infrastructure recovery budget per logical step.
            max_concurrency: Attempts run at once. One by default, so tests on a
                virtual clock stay deterministic.
        """
        self._clock = _VirtualClock(start_time)
        # A store the harness built is the harness's to close. Leaving a
        # pooled store open leaks its connections and its worker threads into
        # every later test in the process.
        self._owned_store = MemoryRunStore() if store is None else None
        self._store: RunStore = store if store is not None else self._owned_store  # pyright: ignore[reportAttributeAccessIssue]
        self._workflow_classes = workflow_classes
        self._runtime_kwargs: dict[str, Any] = {
            "lease_duration": parse_duration(lease_duration),
            "lease_renew_interval": lease_renew_interval,
            "observer": observer,
            "max_recoveries": max_recoveries,
            "max_concurrency": max_concurrency,
        }
        self._runtime = self._build_runtime()
        self._token = None

    def _build_runtime(self) -> WorkflowRuntime:
        """Construct a runtime on the harness's store, clock, and classes.

        Returns:
            The registered, not yet started, runtime.
        """
        # alerts=None: a developer's shell may name a real Slack hook, and a
        # test that fails a run on purpose must never page anyone.
        runtime = WorkflowRuntime(
            self._store,
            clock=self._clock,
            rng=lambda: 1.0,
            alerts=None,
            **self._runtime_kwargs,
        )
        for workflow_cls in self._workflow_classes:
            runtime.register(workflow_cls)
        return runtime

    @property
    def now(self) -> float:
        """The current virtual time.

        Returns:
            The time in epoch seconds.
        """
        return self._clock.now

    @property
    def runtime(self) -> WorkflowRuntime:
        """The harness's workflow runtime.

        Returns:
            The runtime.
        """
        return self._runtime

    @property
    def kernel(self) -> WorkflowKernel:
        """The harness's kernel.

        Returns:
            The kernel.
        """
        return self._runtime.kernel

    async def __aenter__(self) -> WorkflowTestHarness:
        """Start the runtime without a background worker.

        Returns:
            The harness.
        """
        await self._runtime.startup(start_worker=False)
        self._token = _context_runtime.set(self._runtime)
        return self

    async def __aexit__(self, *exc_info) -> None:
        """Deactivate and shut down the runtime.

        Args:
            exc_info: The exception info, if any.
        """
        if self._token is not None:
            _context_runtime.reset(self._token)
            self._token = None
        await self._runtime.shutdown()
        closer = getattr(self._owned_store, "close", None)
        if closer is not None:
            closed = closer()
            if inspect.isawaitable(closed):
                await closed

    async def start(
        self,
        target: Any,
        *,
        request_key: str | None = None,
        labels: dict[str, str] | None = None,
    ) -> StartResult:
        """Start a run and process work until idle.

        Any root can be started here, whatever trigger it declares: in a test
        the author is the webhook provider and the scheduler.

        Args:
            target: The root event, e.g. ``MyWorkflow.begin(payload)``.
            request_key: Idempotent admission key.
            labels: Server-derived indexing labels.

        Returns:
            The admission result.
        """
        result = await self.kernel.start(
            target, request_key=request_key, labels=labels, trigger_kind=None
        )
        await self.kernel.run_until_idle()
        return result

    async def start_only(
        self,
        target: Any,
        *,
        request_key: str | None = None,
        labels: dict[str, str] | None = None,
    ) -> StartResult:
        """Admit a run without executing anything.

        Crash and contention tests need the admitted-but-unclaimed state so
        they can play the doomed worker themselves; ``start`` would run the
        root step before returning.

        Args:
            target: The root event, e.g. ``MyWorkflow.begin(payload)``.
            request_key: Idempotent admission key.
            labels: Server-derived indexing labels.

        Returns:
            The admission result.
        """
        return await self.kernel.start(
            target, request_key=request_key, labels=labels, trigger_kind=None
        )

    async def run_until_idle(self) -> None:
        """Process work until nothing is claimable at the current time."""
        await self.kernel.run_until_idle()

    async def advance(self, duration: DurationLike) -> None:
        """Advance the virtual clock and process any work that became due.

        Args:
            duration: How far to advance, e.g. ``"2d"``.
        """
        self._clock.now += parse_duration(duration)
        await self.kernel.run_until_idle()

    async def get_run(self, run_id: str) -> RunSnapshot | None:
        """Load a read-only snapshot of a run.

        Args:
            run_id: The run identity.

        Returns:
            The snapshot, or None if the run is unknown.
        """
        return await self.kernel.get_run(run_id)

    async def resume(self, run_id: str) -> bool:
        """Re-open a suspended run and process the work it unblocks.

        Args:
            run_id: The run to resume.

        Returns:
            True if a suspended run was re-opened.
        """
        resumed = await self.kernel.resume(run_id)
        await self.kernel.run_until_idle()
        return resumed

    async def signal(
        self, run_id: str, delivery: Any, *, key: str | None = None
    ) -> Any:
        """Deliver a signal and process the work it unblocks.

        Args:
            run_id: The receiving run.
            delivery: The addressed payload, e.g. ``MyFlow.approved(value)``.
            key: Sender idempotency key.

        Returns:
            What the store did with the delivery.
        """
        disposition = await self.kernel.signal(run_id, delivery, key=key)
        await self.kernel.run_until_idle()
        return disposition

    async def cancel(self, run_id: str) -> bool:
        """Request cancellation of a run and process the drain.

        Args:
            run_id: The run to cancel.

        Returns:
            True if intent was recorded on a nonterminal run.
        """
        cancelled = await self.kernel.cancel(run_id)
        await self.kernel.run_until_idle()
        return cancelled

    async def retry(self, run_id: str) -> bool:
        """Re-open a failed run at the step that failed, and drain.

        Args:
            run_id: The failed run to retry.

        Returns:
            True if a failed run was re-opened.
        """
        retried = await self.kernel.retry(run_id)
        await self.kernel.run_until_idle()
        return retried

    async def skip(self, run_id: str) -> bool:
        """Give up on a blocking step and let the run carry on, then drain.

        Args:
            run_id: The stuck run to unstick.

        Returns:
            True if a blocking step was skipped.
        """
        skipped = await self.kernel.skip(run_id)
        await self.kernel.run_until_idle()
        return skipped

    async def history(self, run_id: str) -> tuple[HistoryEvent, ...]:
        """A run's whole recorded story, oldest first.

        Args:
            run_id: The run.

        Returns:
            Its history events.
        """
        return await self._store.get_history(run_id)

    async def children(self, run_id: str) -> tuple[RunRecord, ...]:
        """The child runs a run fanned out to, across all of its join slots.

        Args:
            run_id: The parent run.

        Returns:
            The children, in join-slot order.
        """
        snapshot = await self.get_run(run_id)
        if snapshot is None:
            return ()
        kids: tuple[RunRecord, ...] = ()
        for step in snapshot.steps:
            if step.origin == "join":
                kids = (*kids, *await self._store.list_children(run_id, step.ordinal))
        return kids

    async def run_until_terminal(
        self, run_id: str, *, within: DurationLike = "30d"
    ) -> RunSnapshot:
        """Drive a run to a terminal state, advancing time as its waits need.

        Runs everything currently due, then jumps the virtual clock to the
        next timer or schedule and repeats -- the test says what should
        happen, not how long each wait was.

        Args:
            run_id: The run to finish.
            within: The most virtual time to spend before giving up.

        Returns:
            The terminal snapshot.

        Raises:
            AssertionError: If the run is not terminal within the budget, or
                nothing is due and nothing ever will be -- a run waiting on a
                signal no test sends.
        """
        deadline = self.now + parse_duration(within)
        while True:
            await self.run_until_idle()
            snapshot = await self.get_run(run_id)
            assert snapshot is not None, f"no run {run_id!r}"
            if snapshot.status in TERMINAL_RUN_STATUSES:
                return snapshot
            due = [
                when
                for when in (
                    await self._store.next_due(self.now),
                    self.kernel._next_schedule_due(self.now),
                )
                if when is not None
            ]
            if not due:
                msg = (
                    f"Run {run_id!r} is {snapshot.status.value} with nothing due: "
                    "it is waiting on a signal or approval this test never sends."
                )
                raise AssertionError(msg)
            target = max(min(due), self.now + 1e-3)
            if target > deadline:
                msg = (
                    f"Run {run_id!r} is still {snapshot.status.value} after "
                    f"{within}; the next wake is {target - self.now:.0f}s out."
                )
                raise AssertionError(msg)
            await self.advance(target - self.now)

    async def webhook(
        self,
        topic: str,
        payload: Any,
        *,
        headers: Mapping[str, str] | None = None,
        body: bytes | None = None,
    ) -> tuple[int, Any]:
        """Deliver a provider webhook to the runtime's ingress, in-process.

        Drives the same endpoint a deployment mounts, on this loop, so
        verification, deduplication, correlation, and parking all run for
        real; only the network is skipped.

        Args:
            topic: The webhook topic.
            payload: The JSON payload; ignored when ``body`` is given.
            headers: Request headers, e.g. a signature.
            body: The raw body to send instead of encoding ``payload``.

        Returns:
            The response status and decoded JSON body.
        """
        import json

        from starlette.requests import Request

        from reflex.workflow.ingress import webhook_endpoint

        raw = body if body is not None else json.dumps(payload).encode()
        sent = {"content-type": "application/json", **(headers or {})}
        scope = {
            "type": "http",
            "method": "POST",
            "path": f"/_workflow/webhook/{topic}",
            "path_params": {"topic": topic},
            "query_string": b"",
            "headers": [
                (name.lower().encode(), value.encode()) for name, value in sent.items()
            ],
        }
        delivered = False

        async def receive() -> dict[str, Any]:  # noqa: RUF029
            """Hand the body to the request exactly once.

            Returns:
                The ASGI receive message.
            """
            nonlocal delivered
            if delivered:
                return {"type": "http.disconnect"}
            delivered = True
            return {"type": "http.request", "body": raw, "more_body": False}

        response = await webhook_endpoint(self._runtime)(Request(scope, receive))
        return response.status_code, json.loads(bytes(response.body) or b"null")

    async def restart(self) -> None:
        """Replace the runtime with a fresh one on the same store and clock.

        The test for "would this survive a deploy": every run, cursor, lease,
        and parked delivery is whatever the store says it is, and the new
        runtime has to pick up from there with nothing carried in memory.
        """
        if self._token is not None:
            _context_runtime.reset(self._token)
            self._token = None
        await self._runtime.shutdown()
        self._runtime = self._build_runtime()
        await self._runtime.startup(start_worker=False)
        self._token = _context_runtime.set(self._runtime)

    async def force_complete(self, run_id: str, result: Any = None) -> bool:
        """Finish a drained run by operator decision, then drain.

        Args:
            run_id: The run to complete.
            result: The result to record as what it produced.

        Returns:
            True if the run was finalized.
        """
        return await self._force(run_id, RunStatus.COMPLETED, result=result)

    async def force_fail(self, run_id: str, reason: str) -> bool:
        """Fail a drained run by operator decision, then drain.

        Args:
            run_id: The run to fail.
            reason: The message to record as the failure.

        Returns:
            True if the run was finalized.
        """
        return await self._force(run_id, RunStatus.FAILED, error={"message": reason})

    async def _force(
        self,
        run_id: str,
        status: RunStatus,
        *,
        result: Any = None,
        error: dict[str, Any] | None = None,
    ) -> bool:
        """Force-finalize a run and process what its close unblocks.

        Args:
            run_id: The run to finalize.
            status: The terminal status to record.
            result: Result to record when completing.
            error: Error payload to record when failing.

        Returns:
            True if the run was finalized.
        """
        finalized = await self.kernel.force_finalize(
            run_id, status=status, result=result, error=error
        )
        await self.kernel.run_until_idle()
        return finalized
