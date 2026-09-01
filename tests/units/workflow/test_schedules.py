"""Tests for cron schedule triggers."""

import datetime as dt

import pytest
from reflex_base.utils.exceptions import WorkflowDefinitionError
from reflex_base.workflow import WorkflowConfig, schedule

import reflex as rx
from reflex.workflow.cron import CronSchedule
from reflex.workflow.definition import compile_workflow
from reflex.workflow.records import RunStatus
from reflex.workflow.store import MemoryRunStore
from reflex.workflow.testing import WorkflowTestHarness


class _Clock:
    """A manually advanced epoch-seconds clock."""

    def __init__(self, now: float):
        """Start the clock.

        Args:
            now: The starting time in epoch seconds.
        """
        self.now = now

    def __call__(self) -> float:
        """Read the clock.

        Returns:
            The current time in epoch seconds.
        """
        return self.now


# A Tuesday at 12:00 UTC, chosen so quarter-hour schedules are 15 minutes away.
START = dt.datetime(2026, 8, 18, 12, 0, tzinfo=dt.UTC).timestamp()


def _at(expression: str, after: float = START) -> str:
    """Format the next occurrence of an expression for readable assertions.

    Args:
        expression: The cron expression.
        after: Epoch seconds to search from.

    Returns:
        The occurrence as ``"Day YYYY-MM-DD HH:MM"`` in UTC.
    """
    occurrence = CronSchedule(expression).next_after(after)
    assert occurrence is not None
    return dt.datetime.fromtimestamp(occurrence, tz=dt.UTC).strftime(
        "%a %Y-%m-%d %H:%M"
    )


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("*/15 * * * *", "Tue 2026-08-18 12:15"),
        ("0 * * * *", "Tue 2026-08-18 13:00"),
        ("0 9 * * 1", "Mon 2026-08-24 09:00"),
        ("30 2 1 * *", "Tue 2026-09-01 02:30"),
        ("0 0 1 1 *", "Fri 2027-01-01 00:00"),
        ("0 12 * * 3", "Wed 2026-08-19 12:00"),
    ],
)
def test_next_occurrence(expression, expected):
    assert _at(expression) == expected


def test_day_of_month_or_day_of_week():
    """With both day fields restricted, either one matching is a match."""
    # The 21st is a Friday, so the Friday rule fires before the 13th does.
    assert _at("0 12 13 * 5") == "Fri 2026-08-21 12:00"
    # With only day-of-month restricted, weekdays are irrelevant.
    assert _at("0 12 13 * *") == "Sun 2026-09-13 12:00"


@pytest.mark.parametrize(
    "expression",
    ["* * * *", "* * * * * *", "60 * * * *", "* 24 * * *", "*/0 * * * *", "a * * * *"],
)
def test_invalid_expressions_are_rejected(expression):
    with pytest.raises(WorkflowDefinitionError):
        CronSchedule(expression)


def test_occurrences_between_is_bounded():
    """Catch-up after an outage is capped so a restart cannot stampede."""
    every_ten = CronSchedule("*/10 * * * *")
    assert len(every_ten.occurrences_between(START, START + 3600, limit=4)) == 4
    assert len(every_ten.occurrences_between(START, START + 3600, limit=100)) == 6


def test_invalid_cron_is_rejected_at_compile_time(forked_registration_context):
    class BadSchedule(rx.State):
        __workflow__ = WorkflowConfig(id="ops.bad_schedule")

        @rx.event(durable=True, trigger=schedule("0 99 * * *"), effect="none")
        def sweep(self):
            pass

    with pytest.raises(WorkflowDefinitionError, match="out of range"):
        compile_workflow(BadSchedule)


async def test_schedule_fires_on_the_virtual_clock(forked_registration_context):
    fires = []

    class Sweeper(rx.State):
        __workflow__ = WorkflowConfig(id="ops.sweeper")
        ran: int = 0

        @rx.event(durable=True, trigger=schedule("*/15 * * * *"), effect="read")
        def sweep(self):
            fires.append(1)
            self.ran = 1

    async with WorkflowTestHarness(Sweeper, start_time=START) as harness:
        # Deploying a schedule never backfills the past.
        await harness.run_until_idle()
        assert fires == []

        await harness.advance("16m")
        assert len(fires) == 1

        await harness.advance("31m")
        assert len(fires) == 3

        runs = await harness.kernel.list_runs()
        assert len(runs) == 3
        assert all(run.status is RunStatus.COMPLETED for run in runs)
        # One run per occurrence, keyed by the occurrence time.
        assert len({run.request_key for run in runs}) == 3


async def test_occurrences_are_admitted_once_across_restarts(
    forked_registration_context, tmp_path
):
    """A restart re-fires nothing: occurrence keys deduplicate admission."""
    from reflex.workflow.store import SqliteRunStore

    class Restarted(rx.State):
        __workflow__ = WorkflowConfig(id="ops.restarted")
        ran: int = 0

        @rx.event(durable=True, trigger=schedule("*/15 * * * *"), effect="read")
        def sweep(self):
            self.ran += 1

    db_path = tmp_path / "workflow.db"
    first = SqliteRunStore(db_path)
    async with WorkflowTestHarness(Restarted, store=first, start_time=START) as harness:
        await harness.advance("16m")
        assert len(await harness.kernel.list_runs()) == 1
        resume_at = harness.now
    first.close()

    # A second process starts with a cursor at its own "now" and must not
    # re-admit the occurrence the first one already handled.
    second = SqliteRunStore(db_path)
    async with WorkflowTestHarness(
        Restarted, store=second, start_time=resume_at - 300
    ) as harness:
        await harness.advance("10m")
        assert len(await harness.kernel.list_runs()) == 1
    second.close()


async def test_schedule_root_cannot_be_started_by_application_code(
    forked_registration_context,
):
    from reflex_base.utils.exceptions import WorkflowRuntimeError

    class Cronly(rx.State):
        __workflow__ = WorkflowConfig(id="ops.cronly")

        @rx.event(durable=True, trigger=schedule("0 0 * * *"), effect="none")
        def sweep(self):
            pass

    async with WorkflowTestHarness(Cronly, start_time=START) as harness:
        with pytest.raises(WorkflowRuntimeError, match="cannot be started here"):
            await harness.kernel.start(Cronly.sweep)


async def test_a_restart_resumes_the_schedule_cursor(forked_registration_context):
    """A worker that restarts catches up instead of skipping the downtime.

    With the cursor only in memory, a process starting up treats every
    occurrence that happened while it was down as already fired -- the hourly
    report simply does not run for the hour you were deploying, and nothing
    records that it was skipped.
    """
    fired: list[float] = []

    class Hourly(rx.State):
        __workflow__ = WorkflowConfig(id="sched.restart")

        @rx.event(durable=True, trigger=schedule("0 * * * *"), effect="none")
        def tick(self):
            """Note the occurrence."""
            fired.append(1)

    store = MemoryRunStore()
    async with WorkflowTestHarness(Hourly, store=store) as harness:
        await harness.advance("90m")
        first_count = len(fired)
        assert first_count >= 1

    # A new process on the same store: the cursor survived, so the hours that
    # passed while nothing was running are caught up rather than skipped.
    async with WorkflowTestHarness(
        Hourly, store=store, start_time=harness.now + 7200
    ) as resumed:
        await resumed.advance("1m")

    assert len(fired) > first_count, "the restarted worker skipped the downtime"


async def test_skipped_catchup_is_counted_out_loud(forked_registration_context, capsys):
    """Occurrences the cap drops are named, never silently lost.

    A worker down for a week comes back to hundreds of missed quarter-hour
    occurrences; it catches up the cap's worth and jumps the cursor. Without
    the warning, the jump reads as "covered" and the missing runs are only
    discovered by whoever needed their output.
    """
    from reflex.workflow.kernel import MAX_SCHEDULE_CATCHUP, WorkflowKernel

    class Nightly(rx.State):
        __workflow__ = WorkflowConfig(id="sched.lossy")

        @rx.event(durable=True, effect="none", trigger=schedule("*/15 * * * *"))
        def tick(self):
            """Fire on the quarter hour.

            Returns:
                Completion.
            """
            return rx.complete(result=None)

    clock = _Clock(1_000_000.0)
    store = MemoryRunStore()
    kernel = WorkflowKernel([compile_workflow(Nightly)], store, clock=clock)
    await kernel.run_until_idle()

    clock.now += 7 * 24 * 3600  # a week of downtime
    admitted = await kernel._admit_due_schedules(clock.now)  # pyright: ignore[reportPrivateUsage]
    assert admitted == MAX_SCHEDULE_CATCHUP
    err = capsys.readouterr()
    assert "missed more than" in err.out + err.err, (
        "the skipped remainder must be named, not silently jumped over"
    )


async def test_a_paused_schedule_skips_and_resuming_never_backfills(
    forked_registration_context,
):
    """Pause for three hours of an hourly schedule: zero runs, cursor moved.

    Resuming then yields exactly the next occurrence -- an operator who paused
    a nightly job for a week wants one run when they resume, not seven.
    """
    fired: list[float] = []

    class Hourly(rx.State):
        __workflow__ = WorkflowConfig(id="sched.pausable")

        @rx.event(durable=True, trigger=schedule("0 * * * *"), effect="none")
        def tick(self):
            """Note the occurrence."""
            fired.append(1)

    store = MemoryRunStore()
    async with WorkflowTestHarness(Hourly, store=store) as harness:
        await harness.advance("61m")
        assert len(fired) == 1, "the schedule works before it is paused"

        await store.set_schedule_paused("sched.pausable:tick", True, harness.now)
        await harness.advance("3h")
        assert len(fired) == 1, "paused: three occurrences skipped"
        cursor = await store.read_schedule_cursor("sched.pausable:tick")
        assert cursor is not None
        assert cursor >= harness.now - 60, "the cursor kept moving while paused"

        await store.set_schedule_paused("sched.pausable:tick", False, harness.now)
        await harness.advance("61m")
        assert len(fired) == 2, "resumed: exactly the next occurrence, no backfill"
