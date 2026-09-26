"""02 · Send a weekly business update.

Pass condition: the report uses the intended timezone and date range, marks
missing data clearly, and does not send twice after a retry.
"""

from __future__ import annotations

import datetime
import uuid
import zoneinfo

import pytest
from examples.ex02_weekly_update import SALES, WeeklyUpdate, week_before
from examples.services import world
from reflex_workflow.engine import runtime
from sqlalchemy import insert

from .conftest import eventually

pytestmark = pytest.mark.asyncio(loop_scope="module")

PACIFIC = zoneinfo.ZoneInfo("America/Los_Angeles")
# 08:00 Monday 21 September 2026, Pacific: when the report is meant to run.
SCHEDULED = datetime.datetime(2026, 9, 21, 8, 0, tzinfo=PACIFIC)


async def run_report(name: str, scheduled: datetime.datetime, tz: str) -> WeeklyUpdate:
    """Run one occurrence of a report as if the schedule had just fired.

    Args:
        name: Which report to run.
        scheduled: The time the occurrence was due.
        tz: The report's timezone.

    Returns:
        The row after the run.
    """
    rt = runtime.current()
    async with rt.session_factory() as session, session.begin():
        await session.execute(
            insert(WeeklyUpdate).values(
                name=name,
                timezone=tz,
                status="new",
                next_step="collect",
                wake_at=scheduled,
                attempts=0,
                wf_version=0,
            )
        )

    async def shared() -> bool:
        """Tell whether the report has been shared.

        Returns:
            Whether it has.
        """
        row = await WeeklyUpdate.by(WeeklyUpdate.name == name).get()
        return row is not None and row.status == "shared"

    await eventually(shared)
    row = await WeeklyUpdate.by(WeeklyUpdate.name == name).get()
    assert row is not None
    return row


async def test_the_week_is_the_one_that_ended_in_the_reports_timezone(running):
    days = week_before(SCHEDULED, "America/Los_Angeles")
    assert (days[0], days[-1]) == (
        datetime.date(2026, 9, 14),
        datetime.date(2026, 9, 20),
    )

    # Sunday evening in California is already Monday in Auckland, so the week
    # that has just ended there is the later one, and the report says so.
    sunday_evening = datetime.datetime(2026, 9, 20, 20, 0, tzinfo=PACIFIC)
    SALES.clear()
    row = await run_report(
        f"week-{uuid.uuid4().hex}", sunday_evening, "Pacific/Auckland"
    )
    assert row.report is not None
    assert row.report["week_start"] == "2026-09-14"
    assert week_before(sunday_evening, "America/Los_Angeles")[0] == datetime.date(
        2026, 9, 7
    )


async def test_the_report_totals_the_scheduled_week(running):
    SALES.clear()
    SALES.update({
        datetime.date(2026, 9, 14) + datetime.timedelta(days=offset): 100 + offset
        for offset in range(7)
    })
    # A day outside the window must not be counted.
    SALES[datetime.date(2026, 9, 21)] = 9999

    row = await run_report(f"week-{uuid.uuid4().hex}", SCHEDULED, "America/Los_Angeles")
    assert row.report is not None
    assert row.report["week_start"] == "2026-09-14"
    assert row.report["week_end"] == "2026-09-20"
    assert row.report["total"] == sum(range(100, 107))
    assert row.report["complete"] is True
    assert row.status == "shared"


async def test_missing_days_are_marked_rather_than_silently_zero(running):
    SALES.clear()
    SALES[datetime.date(2026, 9, 14)] = 100

    row = await run_report(f"week-{uuid.uuid4().hex}", SCHEDULED, "America/Los_Angeles")
    assert row.report is not None
    assert row.report["complete"] is False
    assert len(row.report["missing_days"]) == 6
    assert row.report["total"] == 100


async def test_a_failed_send_is_retried_without_a_second_report(running):
    SALES.clear()
    world.break_next("report.publish", times=2)

    row = await run_report(f"week-{uuid.uuid4().hex}", SCHEDULED, "America/Los_Angeles")
    assert row.status == "shared"
    assert world.attempts("report.publish") == 3
    assert len(world.effects("report.publish")) == 1


async def test_the_next_occurrence_is_the_following_monday(running):
    SALES.clear()
    row = await run_report(f"week-{uuid.uuid4().hex}", SCHEDULED, "America/Los_Angeles")
    assert row.next_step == "collect"
    assert row.wake_at is not None
    following = row.wake_at.astimezone(PACIFIC)
    assert (following.date(), following.hour) == (datetime.date(2026, 9, 28), 8)
