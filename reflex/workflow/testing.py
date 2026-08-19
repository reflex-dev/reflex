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
from reflex.workflow.runtime import WorkflowRuntime, _context_runtime
from reflex.workflow.store import MemoryRunStore

if TYPE_CHECKING:
    from reflex_base.workflow import DurationLike

    from reflex.state import BaseState
    from reflex.workflow.kernel import WorkflowKernel
    from reflex.workflow.records import RunSnapshot, StartResult
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
        self._runtime = WorkflowRuntime(
            store if store is not None else self._owned_store,
            clock=self._clock,
            rng=lambda: 1.0,
            lease_duration=parse_duration(lease_duration),
            lease_renew_interval=lease_renew_interval,
            observer=observer,
            max_recoveries=max_recoveries,
            max_concurrency=max_concurrency,
        )
        for workflow_cls in workflow_classes:
            self._runtime.register(workflow_cls)
        self._token = None

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

        Args:
            target: The root event, e.g. ``MyWorkflow.begin(payload)``.
            request_key: Idempotent admission key.
            labels: Server-derived indexing labels.

        Returns:
            The admission result.
        """
        result = await self.kernel.start(target, request_key=request_key, labels=labels)
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
        return await self.kernel.start(target, request_key=request_key, labels=labels)

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
