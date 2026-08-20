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
