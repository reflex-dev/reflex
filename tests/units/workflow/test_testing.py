"""Tests for the test harness itself.

Every other workflow test measures with this instrument, so a defect here
would not fail loudly -- it would quietly invalidate the evidence for
everything else. These assert the properties the rest of the suite assumes:
that time is virtual, that advancing runs exactly what became due, and that
one harness cannot see another's runs.
"""

import time

import pytest
from reflex_base.utils.exceptions import WorkflowDefinitionError
from reflex_base.workflow import WorkflowConfig, manual

import reflex as rx
from reflex.workflow.records import RunStatus
from reflex.workflow.store import MemoryRunStore
from reflex.workflow.testing import WorkflowTestHarness

FIRED: list[str] = []


class Deferred(rx.State):
    """Defers work by a day, then records that it ran."""

    __workflow__ = WorkflowConfig(id="harness.deferred")
    done: bool = False

    @rx.event(durable=True, trigger=manual(), effect="none")
    def go(self):
        """Schedule the follow-up.

        Returns:
            A step due in one day.
        """
        FIRED.append("go")
        return rx.after("1d", Deferred.later)

    @rx.event(durable=True, effect="none")
    def later(self):
        """Run a day later."""
        FIRED.append("later")
        self.done = True


async def test_time_is_virtual_not_wall_clock(forked_registration_context):
    """A day passes in microseconds, and never touches the real clock.

    If the harness slept, a suite with a three-day timer in it would take
    three days; if it read the wall clock, the same test would behave
    differently depending on when it ran.
    """
    FIRED.clear()
    started = time.monotonic()
    async with WorkflowTestHarness(Deferred) as harness:
        before = harness.now
        result = await harness.start(Deferred.go)
        assert result.run_id is not None
        await harness.advance("1d")
        assert harness.now - before == pytest.approx(86_400)
    assert time.monotonic() - started < 5, "the harness slept in real time"
    assert FIRED == ["go", "later"]


async def test_advancing_runs_what_became_due_and_nothing_else(
    forked_registration_context,
):
    """Work due later stays pending; the run is left mid-flight, not finished."""
    FIRED.clear()
    async with WorkflowTestHarness(Deferred) as harness:
        result = await harness.start(Deferred.go)
        assert result.run_id is not None

        await harness.advance("23h")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING
        assert FIRED == ["go"], "a step ran before it was due"

        await harness.advance("1h")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert FIRED == ["go", "later"]


async def test_the_clock_cannot_run_backwards(forked_registration_context):
    """Rewinding time would make due work undue and strand a run."""
    async with WorkflowTestHarness(Deferred) as harness:
        with pytest.raises(WorkflowDefinitionError, match=r"[Dd]uration"):
            await harness.advance("-5s")


async def test_each_harness_starts_from_a_clean_store(forked_registration_context):
    """Two harnesses cannot see each other's runs.

    A shared default store would let one test's leftovers satisfy another
    test's assertion, which is the failure mode that makes a suite untrustable
    rather than merely red.
    """
    FIRED.clear()
    async with WorkflowTestHarness(Deferred) as first:
        result = await first.start(Deferred.go)
        assert result.run_id is not None
        assert len(await first.kernel.list_runs()) == 1

    async with WorkflowTestHarness(Deferred) as second:
        assert await second.kernel.list_runs() == ()
        assert await second.get_run(result.run_id) is None


async def test_an_injected_store_is_left_to_its_owner(forked_registration_context):
    """A store the caller passed in outlives the harness that borrowed it.

    The harness closes what it created; closing what it was handed would
    break the multi-harness tests that share one store on purpose.
    """
    store = MemoryRunStore()
    async with WorkflowTestHarness(Deferred, store=store) as harness:
        result = await harness.start(Deferred.go)
        assert result.run_id is not None

    # Still usable afterwards: the run is there for the next harness.
    assert await store.get_run(result.run_id) is not None
