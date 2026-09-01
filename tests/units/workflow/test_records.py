"""Tests for the scheduling predicates every worker consults.

``step_claimable_at`` and ``step_wake_at`` decide what a worker may take and
how long it may sleep. They are small and pure, they are consulted by three
stores and the kernel, and their subtlest rule is invisible from the call
site: a wait with no deadline must never look claimable, or the worker spins
at full speed forever instead of idling. Nothing asserted them directly --
they were only ever exercised through store behaviour, where a regression
would surface far from its cause.
"""

import dataclasses

import pytest

from reflex.workflow.records import (
    CLAIMABLE_STEP_STATUSES,
    TERMINAL_STEP_STATUSES,
    StepRecord,
    StepStatus,
    attempts_made,
    step_claimable_at,
    step_wake_at,
)

NOW = 1_000.0


def make(status: StepStatus, due_at: float = 0.0) -> StepRecord:
    """Build a step in a given status and due time.

    Args:
        status: The step status.
        due_at: Its due time in epoch seconds.

    Returns:
        The step record.
    """
    return StepRecord(
        run_id="r",
        ordinal=0,
        handler_id="h",
        status=status,
        args={},
        due_at=due_at,
        origin="root",
    )


@pytest.mark.parametrize("status", sorted(CLAIMABLE_STEP_STATUSES, key=str))
def test_a_claimable_step_waits_for_its_due_time(status: StepStatus):
    """Ready, retry-backoff and recovery all gate on the clock alike.

    Args:
        status: The claimable status under test.
    """
    assert step_claimable_at(make(status, NOW - 1), NOW)
    assert step_claimable_at(make(status, NOW), NOW)
    assert not step_claimable_at(make(status, NOW + 1), NOW)
    assert step_wake_at(make(status, NOW + 5)) == NOW + 5


def test_a_wait_becomes_claimable_only_when_its_deadline_arrives():
    """Claiming a blocked slot IS the timeout branch, so it waits for it."""
    assert not step_claimable_at(make(StepStatus.BLOCKED, NOW + 1), NOW)
    assert step_claimable_at(make(StepStatus.BLOCKED, NOW), NOW)
    assert step_wake_at(make(StepStatus.BLOCKED, NOW + 1)) == NOW + 1


def test_a_wait_without_a_deadline_never_wakes_on_the_clock():
    """The rule that keeps an idle worker idle.

    A wait with no deadline is due_at == 0. Treating that as "due since the
    epoch" would make it permanently claimable, and a worker would spin
    through it as fast as it could rather than sleeping until something
    actually happens. It is resolved by a signal, never by time.
    """
    forever = make(StepStatus.BLOCKED, 0.0)
    assert not step_claimable_at(forever, NOW)
    assert not step_claimable_at(forever, 0.0)
    assert step_wake_at(forever) is None


@pytest.mark.parametrize("status", sorted(TERMINAL_STEP_STATUSES, key=str))
def test_a_finished_step_is_never_claimable_again(status: StepStatus):
    """Terminal is terminal, whatever the clock says.

    Args:
        status: The terminal status under test.
    """
    assert not step_claimable_at(make(status, 0.0), NOW)
    assert not step_claimable_at(make(status, NOW - 100), NOW)
    assert step_wake_at(make(status, NOW - 100)) is None


def test_a_claimed_step_is_not_reclaimed_by_the_clock():
    """A step someone is executing is recovered by lease expiry, not due time.

    If the clock could reclaim it, a slow attempt would be raced by the very
    worker that started it.
    """
    running = make(StepStatus.CLAIMED, NOW - 100)
    assert not step_claimable_at(running, NOW)
    assert step_wake_at(running) is None


def test_blocked_is_deliberately_not_in_the_claimable_set():
    """The set and the predicate say different things, on purpose.

    Callers that read CLAIMABLE_STEP_STATUSES do not all bound due_at, so a
    blocked slot must not be a member; the predicate is what knows a deadline
    can make one claimable.
    """
    assert StepStatus.BLOCKED not in CLAIMABLE_STEP_STATUSES
    assert step_claimable_at(make(StepStatus.BLOCKED, NOW), NOW)


def test_a_step_that_worked_first_try_has_made_one_attempt():
    """The retry budget spent nothing, but the handler still ran once.

    ``attempts`` is budget accounting, so a first-try success leaves it at
    zero; a run view that printed that would be telling an operator the step
    never ran.
    """
    assert attempts_made(make(StepStatus.SUCCEEDED)) == 1
    assert attempts_made(make(StepStatus.CLAIMED)) == 1


def test_waiting_steps_count_only_what_has_already_run():
    """Nothing is in flight, so the counters are the whole story."""
    assert attempts_made(make(StepStatus.READY)) == 0
    assert attempts_made(make(StepStatus.BLOCKED)) == 0
    assert (
        attempts_made(dataclasses.replace(make(StepStatus.RETRY_WAIT), attempts=2)) == 2
    )
    assert attempts_made(dataclasses.replace(make(StepStatus.SKIPPED), attempts=1)) == 1


def test_failed_attempts_and_lost_attempts_both_count_as_runs():
    """A crash took the attempt away from the budget, not from history."""
    step = dataclasses.replace(make(StepStatus.SUCCEEDED), attempts=2, recoveries=1)
    assert attempts_made(step) == 4
    lost = dataclasses.replace(make(StepStatus.RECOVERY_WAIT), recoveries=1)
    assert attempts_made(lost) == 1
