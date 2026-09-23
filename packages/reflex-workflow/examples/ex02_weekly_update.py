"""02 · Send a weekly business update.

Every Monday the run collects the week that just ended, totals it, builds a
report, and shares it. The window is taken from the run's own scheduled time
rather than from the clock, so a run that starts late still reports the week it
was scheduled for, and a restart cannot shift the window.
"""

from __future__ import annotations

import datetime
import zoneinfo
from typing import Any

from reflex_workflow import Cron, Workflow, every, step
from sqlalchemy import Date, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from examples.base import Base
from examples.services import world

# What each day contributed, as the analytics store would have it. A day that is
# missing from here is missing data, and the report has to say so.
SALES: dict[datetime.date, int] = {}

# Providers here fail in bursts; a few quick attempts clear most of it.
RETRIES = 3
BACKOFF = datetime.timedelta(milliseconds=50)


def week_before(moment: datetime.datetime, tz: str) -> tuple[datetime.date, ...]:
    """List the days of the week that ended before a moment.

    Args:
        moment: The moment the report is for, usually the run's scheduled time.
        tz: The timezone whose calendar the week is counted on.

    Returns:
        The seven days, Monday first.
    """
    local = moment.astimezone(zoneinfo.ZoneInfo(tz)).date()
    monday = local - datetime.timedelta(days=local.weekday() + 7)
    return tuple(monday + datetime.timedelta(days=offset) for offset in range(7))


class WeeklyUpdate(Base, Workflow):
    """One recurring weekly report."""

    __tablename__ = "example_weekly_update"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    timezone: Mapped[str] = mapped_column(String, default="America/Los_Angeles")
    week_start: Mapped[datetime.date | None] = mapped_column(Date, default=None)
    report: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    status: Mapped[str] = mapped_column(String, default="new")

    @step(retries=RETRIES, backoff=BACKOFF)
    async def collect(self):
        """Total the week that ended at the scheduled time.

        Returns:
            The step that shares the report.
        """
        days = week_before(
            self.wake_at or datetime.datetime.now(datetime.timezone.utc), self.timezone
        )
        self.week_start = days[0]
        missing = [day.isoformat() for day in days if day not in SALES]
        self.report = {
            "week_start": days[0].isoformat(),
            "week_end": days[-1].isoformat(),
            "timezone": self.timezone,
            "total": sum(SALES.get(day, 0) for day in days),
            "missing_days": missing,
            "complete": not missing,
        }
        self.status = "collected"
        return WeeklyUpdate.share

    @step(retries=RETRIES, backoff=BACKOFF)
    async def share(self):
        """Publish the report once for its week, then wait for the next one.

        Returns:
            The schedule for the following week.
        """
        await world.call(
            "report.publish",
            key=f"{self.name}-{self.week_start}",
            channel=self.name,
            **(self.report or {}),
        )
        self.status = "shared"
        return every(WeeklyUpdate.collect, Cron("0 8 * * MON", self.timezone))


async def schedule(name: str, tz: str = "America/Los_Angeles") -> bool:
    """Declare the weekly report, without duplicating it on restart.

    Args:
        name: Which report this is.
        tz: The timezone its week and send time are counted in.

    Returns:
        Whether this call created the schedule.
    """
    return await WeeklyUpdate(name=name, timezone=tz).start(WeeklyUpdate.collect)
