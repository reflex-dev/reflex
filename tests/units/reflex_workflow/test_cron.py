"""Tests for reflex_workflow.cron, including agreement with other cron libraries."""

from __future__ import annotations

import datetime
import random
import zoneinfo

import pytest
from croniter import croniter
from cronsim import CronSim
from reflex_workflow import Cron

UTC = datetime.timezone.utc
PACIFIC = zoneinfo.ZoneInfo("America/Los_Angeles")

# Terms drawn to build random expressions, per field.
TERMS = (
    ["*", "0", "30", "*/5", "0,30", "15-45", "0-59/7", "59"],
    ["*", "0", "9", "*/6", "9-17", "0,12", "23", "1-23/3"],
    ["*", "1", "15", "*/10", "1-7", "28,31", "10-20/4"],
    ["*", "1", "2", "*/3", "JAN-MAR", "6,12", "2-11/2"],
    ["*", "0", "5", "MON", "MON-FRI", "SAT,SUN", "*/2", "5-7"],
)


def expressions(count: int) -> list[str]:
    """Build random five-field expressions.

    Args:
        count: How many to build.

    Returns:
        The expressions.
    """
    rng = random.Random(20260922)
    return [" ".join(rng.choice(terms) for terms in TERMS) for _ in range(count)]


def test_a_schedule_fires_at_the_times_it_names():
    at_nine = Cron("0 9 * * MON-FRI", PACIFIC)
    saturday = datetime.datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    fires = at_nine(saturday).astimezone(PACIFIC)
    assert (fires.hour, fires.minute) == (9, 0)
    # The weekend is skipped, and the time is 9am where the schedule says it is.
    assert fires.date() == datetime.date(2026, 9, 21)
    assert fires == datetime.datetime(2026, 9, 21, 16, 0, tzinfo=UTC)


def test_both_day_fields_match_either_day():
    # Vixie cron ORs the day fields: the 13th, or any Friday.
    friday_the_13th = Cron("0 0 13 * FRI")
    days = []
    when = datetime.datetime(2026, 10, 1, tzinfo=UTC)
    for _ in range(6):
        when = friday_the_13th(when)
        days.append(when.date())
    assert datetime.date(2026, 10, 13) in days
    assert datetime.date(2026, 10, 2) in days


def test_a_restricted_weekday_alone_ignores_the_day_of_month():
    sundays = Cron("0 0 * * SUN")
    when = datetime.datetime(2026, 9, 22, tzinfo=UTC)
    assert all((when := sundays(when)).isoweekday() == 7 for _ in range(5))


@pytest.mark.parametrize(
    "expression",
    [
        "0 9 * *",
        "0 9 * * * *",
        "",
        "60 * * * *",
        "* 24 * * *",
        "0 0 32 * *",
        "0 0 * 13 *",
        "0 0 * * 8",
        "17-5 * * * *",
        "*/0 * * * *",
        "0 0 * * MONDAY",
        "x * * * *",
        "*/x * * * *",
        "*/ * * * *",
        "0 0 * * 1/",
    ],
)
def test_an_expression_that_is_not_valid_is_refused(expression: str):
    with pytest.raises(ValueError):
        Cron(expression)


def test_a_weekday_range_can_end_on_sunday_by_name():
    weekend = Cron("0 9 * * FRI-SUN")
    when = datetime.datetime(2026, 9, 21, 12, tzinfo=UTC)
    days = [(when := weekend(when)).strftime("%a") for _ in range(4)]
    # As croniter reads it; cronsim refuses the expression.
    assert days == ["Fri", "Sat", "Sun", "Fri"]


def test_a_sunday_to_sunday_range_is_sunday_alone():
    sundays = Cron("0 9 * * SUN-SUN")
    when = datetime.datetime(2026, 9, 21, 12, tzinfo=UTC)
    assert all((when := sundays(when)).isoweekday() == 7 for _ in range(3))


def test_a_moment_without_a_timezone_is_refused():
    with pytest.raises(ValueError, match="timezone-aware"):
        Cron("0 9 * * *")(datetime.datetime(2026, 9, 21, 12))


def test_an_expression_that_can_never_fire_is_refused():
    with pytest.raises(ValueError, match="never fires"):
        Cron("0 0 30 2 *")


def test_a_leap_day_schedule_is_accepted():
    leap = Cron("0 0 29 2 *")
    when = leap(datetime.datetime(2026, 9, 22, tzinfo=UTC))
    assert when.date() == datetime.date(2028, 2, 29)


def test_a_daily_time_the_clock_skips_over_still_fires_once():
    # The 2 March 2026 spring change makes 02:30 Pacific skip from 02:00 to 03:00.
    daily = Cron("30 2 * * *", PACIFIC)
    before = datetime.datetime(2026, 3, 7, 12, 0, tzinfo=PACIFIC)
    skipped = daily(before)
    assert skipped.astimezone(PACIFIC).date() == datetime.date(2026, 3, 8)
    assert skipped == datetime.datetime(2026, 3, 8, 10, 30, tzinfo=UTC)
    assert daily(skipped).astimezone(PACIFIC).date() == datetime.date(2026, 3, 9)


def test_a_daily_time_the_clock_repeats_fires_once():
    # On 1 November 2026, 01:30 Pacific happens twice; only the first counts.
    daily = Cron("30 1 * * *", PACIFIC)
    first = daily(datetime.datetime(2026, 10, 31, 12, 0, tzinfo=PACIFIC))
    assert first == datetime.datetime(2026, 11, 1, 8, 30, tzinfo=UTC)
    # The second pass of 01:30 is 09:30 UTC, and is not fired.
    assert daily(first).astimezone(PACIFIC).date() == datetime.date(2026, 11, 2)


def test_every_time_returned_is_later_than_the_one_asked_about():
    minutely = Cron("* * * * *")
    when = datetime.datetime(2026, 9, 22, 12, 0, 30, tzinfo=UTC)
    assert minutely(when) == datetime.datetime(2026, 9, 22, 12, 1, tzinfo=UTC)
    assert minutely(minutely(when)) == datetime.datetime(2026, 9, 22, 12, 2, tzinfo=UTC)


def agrees_on_days(expression: str) -> bool:
    """Report whether croniter reads an expression's day fields as Debian does.

    Debian counts a day field written as a step, like ``*/2``, as a star and then
    requires both day fields to match; croniter counts it as restricted and matches
    either field. They agree when a day field is a plain star, and when neither is
    written as a step.

    Args:
        expression: The expression.

    Returns:
        Whether croniter can be compared on it.
    """
    days = (expression.split()[2], expression.split()[4])
    return "*" in days or not any(field.startswith("*") for field in days)


def following(
    schedule: Cron, start: datetime.datetime, count: int
) -> list[datetime.datetime]:
    """Collect the next times a schedule fires.

    Args:
        schedule: The schedule.
        start: The moment to start from.
        count: How many times to collect.

    Returns:
        The times, in order.
    """
    times = []
    when = start
    for _ in range(count):
        when = schedule(when)
        times.append(when)
    return times


STARTS = [
    datetime.datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
    datetime.datetime(2026, 2, 27, 23, 59, tzinfo=UTC),
    datetime.datetime(2028, 2, 29, 12, 30, tzinfo=UTC),
    datetime.datetime(2026, 12, 31, 23, 58, tzinfo=UTC),
]


@pytest.mark.parametrize("expression", expressions(400))
def test_next_time_agrees_with_cronsim(expression: str):
    """Compare in UTC, where no clock change can make the two differ."""
    schedule = Cron(expression)
    for start in STARTS:
        theirs = CronSim(expression, start)
        assert following(schedule, start, 4) == [next(theirs) for _ in range(4)], (
            f"{expression} from {start} differs from cronsim"
        )


@pytest.mark.parametrize(
    "expression", [e for e in expressions(400) if agrees_on_days(e)]
)
def test_next_time_agrees_with_croniter(expression: str):
    """Compare in UTC, on the expressions croniter reads the way Debian does."""
    schedule = Cron(expression)
    for start in STARTS:
        theirs = croniter(expression, start)
        assert following(schedule, start, 4) == [
            theirs.get_next(datetime.datetime) for _ in range(4)
        ], f"{expression} from {start} differs from croniter"


def test_the_day_fields_follow_debian_where_the_libraries_differ():
    # A stepped day of month with named weekdays: Debian and cronsim require both.
    both = Cron("0 0 10-20/4 * */2")
    first = both(datetime.datetime(2026, 1, 1, tzinfo=UTC))
    assert first == datetime.datetime(2026, 1, 10, tzinfo=UTC)
    theirs = CronSim("0 0 10-20/4 * */2", datetime.datetime(2026, 1, 1, tzinfo=UTC))
    assert first == next(theirs)
    # croniter reads the same expression as "either day", firing a week earlier.
    assert croniter(
        "0 0 10-20/4 * */2", datetime.datetime(2026, 1, 1, tzinfo=UTC)
    ).get_next(datetime.datetime) == datetime.datetime(2026, 1, 3, tzinfo=UTC)
