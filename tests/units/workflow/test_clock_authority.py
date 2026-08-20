"""Workers on the default clock derive time from the store.

Wall clocks skew across a fleet. A worker whose clock runs fast compares its
own idea of now against a peer's lease expiry and reclaims a live claim --
duplicating exactly the work leases exist to protect -- and admits schedule
occurrences before their time. The store is the one thing every worker
shares, so its clock is the authority: a kernel constructed with the default
clock measures its offset against ``store.epoch_time()`` at startup and on
every recovery pass, and reads time through that offset. An explicitly
injected clock (tests, the dev CLI's fast-forward) is authoritative as given
and never synced.
"""

import asyncio
import time

import pytest

from reflex.workflow.kernel import WorkflowKernel
from reflex.workflow.records import RunRecord, RunStatus, StepRecord, StepStatus
from reflex.workflow.store import MemoryRunStore

SKEW = 120.0


class _SkewedStore(MemoryRunStore):
    """A memory store pretending to be a database whose clock differs."""

    async def epoch_time(self) -> float | None:
        """Answer with a clock a fixed distance from this process's.

        Returns:
            Epoch seconds, skewed.
        """
        return time.time() + SKEW


def _due(run_id: str, due_at: float) -> tuple[RunRecord, StepRecord]:
    """Build one run whose root comes due at a given store time.

    Args:
        run_id: The run identity.
        due_at: When the root may be claimed, in store time.

    Returns:
        The run and its root slot.
    """
    now = time.time()
    run = RunRecord(
        run_id=run_id,
        workflow_id="clock.flow",
        definition_digest="d",
        status=RunStatus.PENDING,
        state={},
        state_version=0,
        next_ordinal=1,
        created_at=now,
        updated_at=now,
    )
    step = StepRecord(
        run_id=run_id,
        ordinal=0,
        handler_id="start",
        status=StepStatus.READY,
        args={},
        due_at=due_at,
        origin="root",
        queue="default",
        created_at=now,
        updated_at=now,
    )
    return run, step


async def test_a_default_clock_kernel_adopts_the_store_clock():
    """After one recovery pass, the kernel reads time by the store's clock."""
    kernel = WorkflowKernel([], _SkewedStore())
    assert kernel._clock() == pytest.approx(time.time(), abs=1.0)  # pyright: ignore[reportPrivateUsage]
    await kernel.recover()
    assert kernel._clock() == pytest.approx(time.time() + SKEW, abs=1.0), (  # pyright: ignore[reportPrivateUsage]
        "the offset must be measured, not assumed zero"
    )


async def test_store_time_decides_what_is_due_not_the_worker_clock():
    """A timer set in store time fires by store time, from any worker.

    The store clock here runs AHEAD of the process clock, so a worker that
    trusted its own time would refuse work that is genuinely due (and with
    the skew reversed, would claim work early and recover live leases). The
    synced worker claims exactly what the store's clock says is claimable.
    """
    store = _SkewedStore()
    kernel = WorkflowKernel([], store)
    await kernel.recover()

    store_now = time.time() + SKEW
    due_run, due_step = _due("due-now", store_now - 5)
    future_run, future_step = _due("due-later", store_now + 3600)
    await store.admit(due_run, due_step, ())
    await store.admit(future_run, future_step, ())

    claim = await store.claim_next(kernel._clock())  # pyright: ignore[reportPrivateUsage]
    assert claim is not None
    assert claim.run.run_id == "due-now"
    assert await store.claim_next(kernel._clock()) is None, (  # pyright: ignore[reportPrivateUsage]
        "an hour-out timer must not be claimable, whatever the local clock says"
    )


async def test_an_injected_clock_is_never_second_guessed():
    """Tests and fast-forward own their clocks; syncing would break both."""
    virtual = 1_000_000.0
    kernel = WorkflowKernel([], _SkewedStore(), clock=lambda: virtual)
    await kernel.recover()
    assert kernel._clock() == pytest.approx(virtual)  # pyright: ignore[reportPrivateUsage]


async def test_a_store_with_no_clock_of_its_own_stops_being_asked():
    """Single-host stores answer None once, and the process clock stands."""
    kernel = WorkflowKernel([], MemoryRunStore())
    await kernel.recover()
    assert kernel._sync_clock_with_store is False  # pyright: ignore[reportPrivateUsage]
    assert kernel._clock() == pytest.approx(time.time(), abs=1.0)  # pyright: ignore[reportPrivateUsage]


class _IndependentClockStore(MemoryRunStore):
    """A store whose clock is its own, like a database on another machine.

    Deriving it from ``time.time`` would make it jump whenever the worker's
    wall clock jumps, which is exactly the thing under test.
    """

    def __init__(self):
        """Anchor the store's clock to real elapsed time."""
        super().__init__()
        self._base = 1_700_000_000.0
        self._start = time.monotonic()

    async def epoch_time(self) -> float | None:
        """Answer with the store's own clock.

        Returns:
            Epoch seconds, unaffected by the caller's wall clock.
        """
        return self._base + (time.monotonic() - self._start)


async def test_a_backward_wall_clock_jump_does_not_move_store_time(monkeypatch):
    """Time must not go backwards between syncs, whatever the machine does.

    NTP steps, a hypervisor resuming a snapshot, an operator correcting a
    drifted host: all move the wall clock without warning. A worker that
    derives store time by adding a fixed offset to that clock moves with it,
    and renews its lease to a moment that has, from the store's point of
    view, already passed. Its claim lapses while it is still working and a
    peer reclaims the step -- two workers on one attempt, which is the one
    thing leases exist to prevent.

    Args:
        monkeypatch: Used to move the process wall clock.
    """
    wall = [1_600_000_000.0]
    monkeypatch.setattr(time, "time", lambda: wall[0])

    # Passed explicitly because the kernel decides whether to sync by identity
    # against time.time, and monkeypatching replaces the object the default
    # argument was bound to. Without this the sync path silently turns off and
    # the test passes while measuring nothing.
    kernel = WorkflowKernel([], _IndependentClockStore(), clock=time.time)
    assert kernel._sync_clock_with_store is True  # pyright: ignore[reportPrivateUsage]
    await kernel.recover()
    before = kernel._clock()  # pyright: ignore[reportPrivateUsage]

    wall[0] -= 45.0
    after = kernel._clock()  # pyright: ignore[reportPrivateUsage]
    assert after >= before, (
        f"store time went backwards by {before - after:.1f}s when the wall "
        "clock did; a lease renewed against it would lapse early"
    )


async def test_store_time_still_advances_with_real_elapsed_time():
    """Immunity to jumps must not mean the clock stops.

    A clock that never moved would be just as wrong: leases would never
    expire and a crashed worker's step would never be recovered.
    """
    kernel = WorkflowKernel([], _IndependentClockStore())
    await kernel.recover()
    first = kernel._clock()  # pyright: ignore[reportPrivateUsage]
    await asyncio.sleep(0.05)
    second = kernel._clock()  # pyright: ignore[reportPrivateUsage]
    assert second > first
    assert second - first < 5.0, "advancing far faster than real time is also wrong"


async def test_a_new_schedule_is_seeded_from_store_time_not_worker_time():
    """A slow worker must not backfill a schedule from before the deploy.

    The seed for a schedule this deployment has never seen is "now". Taken
    from the worker's own clock at construction -- before the first sync --
    "now" on a machine running two minutes slow is two minutes of history,
    and the first sweep admits occurrences that were never meant to run.
    """
    store = _IndependentClockStore()
    kernel = WorkflowKernel([], store)
    assert kernel._started_at is None, "the seed must not be taken before syncing"  # pyright: ignore[reportPrivateUsage]

    await kernel.recover()
    assert kernel._started_at is not None  # pyright: ignore[reportPrivateUsage]
    store_now = await store.epoch_time()
    assert store_now is not None
    assert abs(kernel._started_at - store_now) < 1.0, (  # pyright: ignore[reportPrivateUsage]
        "the seed must sit on the store's clock, not the worker's"
    )
