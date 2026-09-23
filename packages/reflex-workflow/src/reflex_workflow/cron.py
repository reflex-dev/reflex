"""Standard five-field cron expressions and the times they fire."""

from __future__ import annotations

import datetime
import zoneinfo

# Each field's bounds, in the order the fields are written.
BOUNDS = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))

# fmt: off
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun",
          "jul", "aug", "sep", "oct", "nov", "dec"]
DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
# fmt: on

# Days to look ahead before calling an expression unsatisfiable; the sparsest
# standard expression, February 29th, comes round at most every eight years.
SEARCH_DAYS = 366 * 9


def parse_name(value: str, field: int) -> str:
    """Turn a month or weekday name into its number.

    Args:
        value: One term of a field, which may be a name.
        field: Which field it belongs to, counting from the minute.

    Returns:
        The value with any name replaced by its number.
    """
    names = MONTHS if field == 3 else DAYS if field == 4 else ()
    lowered = value.lower()
    return (
        str(names.index(lowered) + (1 if field == 3 else 0))
        if lowered in names
        else value
    )


def parse_field(field: str, index: int) -> frozenset[int]:
    """Turn one cron field into the set of values it matches.

    Args:
        field: The field, e.g. ``*/5`` or ``MON-FRI``.
        index: Which field it is, counting from the minute.

    Returns:
        The values it matches.

    Raises:
        ValueError: If the field is not a valid cron field.
    """
    low, high = BOUNDS[index]
    matched: set[int] = set()
    for term in field.split(","):
        part, slash, step_text = term.partition("/")
        if slash and not step_text:
            msg = f"{term!r} has a slash but no step."
            raise ValueError(msg)
        try:
            step = int(step_text) if step_text else 1
        except ValueError:
            msg = f"{term!r} has a step that is not a number."
            raise ValueError(msg) from None
        if step < 1:
            msg = f"{term!r} has a step below one."
            raise ValueError(msg)
        if part == "*":
            first, last = low, high
        else:
            start, dash, end = part.partition("-")
            try:
                first = int(parse_name(start, index))
                last = (
                    int(parse_name(end, index))
                    if dash
                    else (high if step_text else first)
                )
                # A range that ends on Sunday by name, like FRI-SUN, ends on 7.
                if index == 4 and dash and end.lower() == "sun":
                    last = 7
            except ValueError:
                msg = f"{term!r} is not a number, a name, or a range."
                raise ValueError(msg) from None
        if not (low <= first <= high and low <= last <= high):
            msg = f"{term!r} is outside {low}-{high}."
            raise ValueError(msg)
        if first > last:
            msg = f"{term!r} counts down; write it as two terms."
            raise ValueError(msg)
        values = range(first, last + 1, step)
        # Sunday is written as either 0 or 7, so a range like FRI-SUN stays
        # ascending and folds only once it is expanded.
        if index == 4:
            matched.update(value % 7 for value in values)
        else:
            matched.update(values)
    return frozenset(matched)


class Cron:
    """A cron expression, and the times it fires in one timezone.

    Supports the five standard fields -- minute, hour, day of month, month, day of
    week -- with ``*``, lists, ranges, steps, and month and weekday names. Calling
    it returns the next time it fires after a given moment, so it can be passed to
    ``every`` wherever a schedule is wanted.
    """

    def __init__(
        self, expression: str, tz: str | datetime.tzinfo = datetime.timezone.utc
    ) -> None:
        """Parse an expression, rejecting one that is malformed or never fires.

        Args:
            expression: A five-field cron expression, e.g. ``0 9 * * MON-FRI``.
            tz: The timezone its times are written in.

        Raises:
            ValueError: If the expression is malformed or can never fire.
        """
        fields = expression.split()
        if len(fields) != 5:
            msg = (
                f"{expression!r} must have five fields: minute, hour, day of month, "
                "month, and day of week."
            )
            raise ValueError(msg)
        self.expression = expression
        self.tz = zoneinfo.ZoneInfo(tz) if isinstance(tz, str) else tz
        self.minutes, self.hours, self.days, self.months, self.weekdays = tuple(
            parse_field(field, index) for index, field in enumerate(fields)
        )
        # Vixie cron matches both day fields when either is written as a star,
        # and either field when both name particular days.
        self.both_days = fields[2].startswith("*") or fields[4].startswith("*")
        try:
            self(datetime.datetime.now(datetime.timezone.utc))
        except ValueError:
            msg = f"{expression!r} never fires."
            raise ValueError(msg) from None

    def __repr__(self) -> str:
        """Name the expression in reprs and error messages.

        Returns:
            The expression's repr.
        """
        return f"Cron({self.expression!r}, {self.tz!s})"

    def matches_day(self, day: datetime.date) -> bool:
        """Report whether the expression fires on a date.

        Args:
            day: The date.

        Returns:
            Whether the day's fields match.
        """
        if day.month not in self.months:
            return False
        # isoweekday is Monday 1 through Sunday 7; cron counts Sunday as 0.
        by_day, by_weekday = day.day in self.days, day.isoweekday() % 7 in self.weekdays
        return (by_day and by_weekday) if self.both_days else (by_day or by_weekday)

    def __call__(self, after: datetime.datetime) -> datetime.datetime:
        """Return the first time the expression fires after a moment.

        Times are matched on the clock in this expression's timezone. A time that
        the clock skips over in spring fires at the equivalent moment after the
        jump, and one the clock repeats in autumn fires on its first pass only, so
        a schedule fires once either way.

        Args:
            after: The moment to search from.

        Returns:
            The next time it fires, always later than ``after``.

        Raises:
            ValueError: If ``after`` has no timezone, or the expression does not
                fire within the next nine years.
        """
        if after.tzinfo is None:
            msg = "Cron needs a timezone-aware moment to search from."
            raise ValueError(msg)
        local = after.astimezone(self.tz)
        cursor = local.replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)
        hours, minutes = sorted(self.hours), sorted(self.minutes)
        for _ in range(SEARCH_DAYS):
            if self.matches_day(cursor.date()):
                for hour in hours:
                    if hour < cursor.hour:
                        continue
                    for minute in minutes:
                        if hour == cursor.hour and minute < cursor.minute:
                            continue
                        fires = cursor.replace(hour=hour, minute=minute).astimezone(
                            datetime.timezone.utc
                        )
                        # A repeated hour can put a later clock time at an earlier
                        # moment; those have already fired.
                        if fires > after:
                            return fires
            cursor = (cursor + datetime.timedelta(days=1)).replace(hour=0, minute=0)
        msg = f"{self.expression!r} does not fire within {SEARCH_DAYS // 366} years."
        raise ValueError(msg)
