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

from typing import TYPE_CHECKING, Any

from reflex_base.workflow import DEFAULT_LEASE_DURATION, parse_duration

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
    ):
        """Initialize the harness.

        Args:
            workflow_classes: Workflow classes to register.
            store: Run store override; defaults to a fresh in-memory store.
            start_time: Initial virtual time in epoch seconds.
            lease_duration: Virtual seconds a claim survives without renewal.
            lease_renew_interval: Real seconds between lease renewals.
        """
        self._clock = _VirtualClock(start_time)
        self._runtime = WorkflowRuntime(
            store if store is not None else MemoryRunStore(),
            clock=self._clock,
            rng=lambda: 1.0,
            lease_duration=parse_duration(lease_duration),
            lease_renew_interval=lease_renew_interval,
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
