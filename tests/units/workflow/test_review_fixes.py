"""Fixes for defects an external review found by driving the engine hard.

Each of these was reproduced before it was fixed, and each is here because
the failure was quiet: a wrong run cancelled, a schedule that never fires, a
backoff that never elapses, an operator result that one store keeps and
another rejects.
"""

import decimal

import pytest
from reflex_base.utils.exceptions import WorkflowDefinitionError
from reflex_base.workflow import Retry

from reflex.workflow.cron import MAX_SEARCH_DAYS, CronSchedule
from reflex.workflow.kernel import WorkflowKernel
from reflex.workflow.records import (
    HistoryEventType,
    RunRecord,
    RunStatus,
    StepRecord,
    StepStatus,
)
from reflex.workflow.store import MemoryRunStore, SqliteRunStore

NOW = 1_000_000.0


def _run(run_id: str = "r1") -> RunRecord:
    """Build a run record.

    Args:
        run_id: The run identity.

    Returns:
        The record.
    """
    return RunRecord(
        run_id=run_id,
        workflow_id="review.flow",
        definition_digest="d",
        status=RunStatus.PENDING,
        state={},
        state_version=0,
        next_ordinal=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _step(run_id: str = "r1") -> StepRecord:
    """Build a step record that is not due yet.

    Args:
        run_id: The owning run.

    Returns:
        The record.
    """
    return StepRecord(
        run_id=run_id,
        ordinal=0,
        handler_id="go",
        status=StepStatus.READY,
        args={},
        due_at=NOW + 3600,
        origin="root",
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.parametrize("kind", ["memory", "sqlite"])
async def test_an_operator_result_faces_the_same_serde_everywhere(kind, tmp_path):
    """One input must not mean three behaviours across the stores.

    Memory kept a live Decimal no other store could hold; SQLite raised a
    bare "not JSON serializable" from inside json.dumps. Neither said what to
    do about it, and the Memory case only became a problem on the day someone
    moved to Postgres.

    Args:
        kind: Which store to build.
        tmp_path: Temporary directory for SQLite.
    """
    store = MemoryRunStore() if kind == "memory" else SqliteRunStore(tmp_path / "s.db")
    await store.admit(_run(), _step(), ((HistoryEventType.RUN_ADMITTED, {}),))
    kernel = WorkflowKernel([], store)
    with pytest.raises(TypeError, match="Decimal is not valid run data"):
        await kernel.force_finalize(
            "r1", status=RunStatus.COMPLETED, result=decimal.Decimal("10.10")
        )


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_a_non_finite_retry_multiplier_is_refused(bad):
    """Every comparison against nan is False, so "< 1.0" let it through.

    The backoff it produced was nan or inf, and a step scheduled for a moment
    that never arrives is simply lost.

    Args:
        bad: The multiplier to reject.
    """
    with pytest.raises(WorkflowDefinitionError, match="finite"):
        Retry(max_attempts=3, multiplier=bad)


def test_the_cron_horizon_reaches_across_a_skipped_leap_century():
    """2100 is not a leap year, so 2096 to 2104 is eight years apart.

    A horizon shorter than that reported "no occurrence" for a schedule that
    was merely far off, which reads identically to a broken expression.
    """
    schedule = CronSchedule("0 0 29 2 *")
    import datetime as dt

    base = dt.datetime(2096, 3, 1, tzinfo=dt.UTC).timestamp()
    found = schedule.next_after(base)
    assert found is not None
    assert dt.datetime.fromtimestamp(found, dt.UTC).date() == dt.date(2104, 2, 29)
    assert MAX_SEARCH_DAYS >= 8 * 366, "the horizon must cover the longest gap"


@pytest.mark.parametrize("expression", ["0 0 30 2 *", "0 0 31 4 *", "0 0 31 6 *"])
def test_a_date_that_cannot_exist_is_refused(expression):
    """A schedule that never fires looks exactly like one that is waiting.

    Args:
        expression: A cron expression naming an impossible date.
    """
    with pytest.raises(WorkflowDefinitionError, match="can never occur"):
        CronSchedule(expression)


@pytest.mark.parametrize("expression", ["0 0 29 2 *", "0 0 31 1 *", "0 0 31 2 1"])
def test_rare_but_possible_dates_are_still_accepted(expression):
    """February 29 is rare, not impossible, and a weekday gives a second path.

    Under cron's day-of-month/day-of-week OR rule, ``0 0 31 2 1`` still fires
    on Mondays in February, so refusing it would be wrong.

    Args:
        expression: A cron expression that can occur.
    """
    assert CronSchedule(expression).expression == expression


def test_dropped_schedule_occurrences_reach_the_metrics():
    """Work the engine decided not to do must not leave only a log line."""
    from reflex.workflow.kernel import CompositeObserver, MetricsObserver

    metrics = MetricsObserver()
    CompositeObserver(metrics).on_schedule_skip("nightly", 42)
    assert metrics.totals["schedule_occurrences_skipped"] == 42
    assert metrics.by_workflow["nightly"]["schedule_occurrences_skipped"] == 42


def test_the_default_observer_ignores_dropped_occurrences_quietly():
    """The base class must stay a no-op so custom observers keep working."""
    from reflex.workflow.kernel import WorkflowObserver

    assert WorkflowObserver().on_schedule_skip("nightly", 1) is None
