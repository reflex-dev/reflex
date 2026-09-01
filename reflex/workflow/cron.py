"""A small UTC cron evaluator for schedule triggers.

Supports the five standard fields (minute, hour, day of month, month, day of
week) with ``*``, single values, ``a-b`` ranges, ``a-b/step`` and ``*/step``
steps, and comma-separated lists. When both day-of-month and day-of-week are
restricted, an occurrence matches if *either* matches, which is the behavior
every other cron implementation has.

Schedules are evaluated in UTC so an occurrence identity never depends on the
server's local timezone or on a daylight-saving transition.
"""

from __future__ import annotations

import datetime as dt
from typing import Final

from reflex_base.utils.exceptions import WorkflowDefinitionError

_FIELD_RANGES: Final = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))

_FIELD_NAMES: Final = ("minute", "hour", "day of month", "month", "day of week")

# The rarest satisfiable date is February 29 across a skipped leap century:
# 2096 to 2104 is eight years, because 2100 is not a leap year. A shorter
# horizon reported "no occurrence" for a schedule that was simply far off.
MAX_SEARCH_DAYS: Final = 3000

_LONGEST_MONTH: Final = (0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _parse_field(spec: str, index: int) -> frozenset[int]:
    """Parse one cron field into the set of values it matches.

    Args:
        spec: The field text, e.g. ``"*/15"`` or ``"1,3,5-7"``.
        index: Which of the five fields this is.

    Returns:
        Every value the field matches.

    Raises:
        WorkflowDefinitionError: If the field is malformed or out of range.
    """
    low, high = _FIELD_RANGES[index]
    name = _FIELD_NAMES[index]
    values: set[int] = set()
    for part in spec.split(","):
        body, _, step_text = part.partition("/")
        try:
            step = int(step_text) if step_text else 1
        except ValueError:
            msg = f"Invalid step {step_text!r} in cron {name} field {spec!r}."
            raise WorkflowDefinitionError(msg) from None
        if step < 1:
            msg = f"Step must be >= 1 in cron {name} field {spec!r}."
            raise WorkflowDefinitionError(msg)
        if body == "*":
            start, end = low, high
        elif "-" in body.lstrip("-"):
            start_text, _, end_text = body.partition("-")
            try:
                start, end = int(start_text), int(end_text)
            except ValueError:
                msg = f"Invalid range {body!r} in cron {name} field {spec!r}."
                raise WorkflowDefinitionError(msg) from None
        else:
            try:
                start = end = int(body)
            except ValueError:
                msg = f"Invalid value {body!r} in cron {name} field {spec!r}."
                raise WorkflowDefinitionError(msg) from None
        if start < low or end > high or start > end:
            msg = f"Cron {name} field {spec!r} is out of range; expected {low}-{high}."
            raise WorkflowDefinitionError(msg)
        values.update(range(start, end + 1, step))
    return frozenset(values)


class CronSchedule:
    """A parsed five-field cron expression evaluated in UTC.

    Attributes:
        expression: The original expression text.
    """

    __slots__ = (
        "_days_of_month",
        "_days_of_week",
        "_dom_restricted",
        "_dow_restricted",
        "_hours",
        "_minutes",
        "_months",
        "expression",
    )

    def __init__(self, expression: str):
        """Parse a cron expression.

        Args:
            expression: A five-field cron expression.

        Raises:
            WorkflowDefinitionError: If the expression does not have five
                fields or any field is malformed.
        """
        fields = expression.split()
        if len(fields) != 5:
            msg = (
                f"Invalid cron expression {expression!r}: expected five fields "
                "(minute hour day month weekday)."
            )
            raise WorkflowDefinitionError(msg)
        self.expression = expression
        self._minutes = _parse_field(fields[0], 0)
        self._hours = _parse_field(fields[1], 1)
        self._days_of_month = _parse_field(fields[2], 2)
        self._months = _parse_field(fields[3], 3)
        self._days_of_week = _parse_field(fields[4], 4)
        self._dom_restricted = fields[2] != "*"
        self._dow_restricted = fields[4] != "*"
        self._assert_reachable()

    def _matches_date(self, day: dt.date) -> bool:
        """Whether a date satisfies the month and day fields.

        Args:
            day: The UTC date to test.

        Returns:
            True when the date matches.
        """
        if day.month not in self._months:
            return False
        # Cron numbers weekdays from Sunday; Python numbers them from Monday.
        dow = (day.weekday() + 1) % 7
        dom_hit = day.day in self._days_of_month
        dow_hit = dow in self._days_of_week
        if self._dom_restricted and self._dow_restricted:
            return dom_hit or dow_hit
        return dom_hit and dow_hit

    def _assert_reachable(self) -> None:
        """Refuse a month and day-of-month pairing that no year can satisfy.

        ``0 0 30 2 *`` parses -- every field is in range -- and then never
        fires, which looks exactly like a schedule that is merely waiting.
        A weekday restriction gives the date a second way to match, so this
        only applies when day-of-month is the only selector.

        Raises:
            WorkflowDefinitionError: If no date can ever match.
        """
        if self._dow_restricted or not self._dom_restricted:
            return
        if any(
            day <= _LONGEST_MONTH[month]
            for month in self._months
            for day in self._days_of_month
        ):
            return
        msg = (
            f"Cron expression {self.expression!r} can never occur: no day in "
            f"{sorted(self._days_of_month)} exists in "
            f"{sorted(self._months)}."
        )
        raise WorkflowDefinitionError(msg)

    def next_after(self, after: float) -> float | None:
        """Find the first occurrence strictly after a point in time.

        Args:
            after: Epoch seconds to search forward from.

        Returns:
            The occurrence time in epoch seconds, or None when the expression
            has no occurrence within the search horizon.
        """
        moment = dt.datetime.fromtimestamp(after, tz=dt.timezone.utc).replace(
            second=0, microsecond=0
        ) + dt.timedelta(minutes=1)
        day = moment.date()
        for offset in range(MAX_SEARCH_DAYS):
            candidate_day = day + dt.timedelta(days=offset)
            if not self._matches_date(candidate_day):
                continue
            first_minute = moment if offset == 0 else None
            for hour in sorted(self._hours):
                for minute in sorted(self._minutes):
                    occurrence = dt.datetime(
                        candidate_day.year,
                        candidate_day.month,
                        candidate_day.day,
                        hour,
                        minute,
                        tzinfo=dt.timezone.utc,
                    )
                    if first_minute is not None and occurrence < first_minute:
                        continue
                    return occurrence.timestamp()
        return None

    def count_between(self, after: float, until: float) -> int:
        """Count occurrences in a half-open interval, without a ceiling.

        ``occurrences_between`` bounds what it returns so a catch-up cannot
        run away. Counting how many were missed is a different question, and
        answering it with a bounded list undercounts a long outage exactly
        when the number matters most.

        Args:
            after: Exclusive lower bound in epoch seconds.
            until: Inclusive upper bound in epoch seconds.

        Returns:
            How many occurrences fall in the interval.
        """
        total = 0
        moment = after
        while True:
            nxt = self.next_after(moment)
            if nxt is None or nxt > until:
                return total
            total += 1
            moment = nxt

    def occurrences_between(
        self, after: float, until: float, *, limit: int
    ) -> list[float]:
        """List occurrences in a half-open interval.

        Args:
            after: Exclusive lower bound in epoch seconds.
            until: Inclusive upper bound in epoch seconds.
            limit: Maximum occurrences to return, bounding catch-up after an
                outage so a restart cannot stampede.

        Returns:
            The occurrence times in ascending order.
        """
        found: list[float] = []
        cursor = after
        while len(found) < limit:
            occurrence = self.next_after(cursor)
            if occurrence is None or occurrence > until:
                break
            found.append(occurrence)
            cursor = occurrence
        return found
