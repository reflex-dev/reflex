"""Moment component for humanized date rendering."""

import dataclasses
from datetime import date, datetime, time, timedelta

from reflex.components.component import NoSSRComponent
from reflex.event import EventHandler, passthrough_event_spec
from reflex.utils.imports import ImportDict
from reflex.vars.base import LiteralVar, Var


@dataclasses.dataclass(frozen=True)
class MomentDelta:
    """A delta used for add/subtract prop in Moment."""

    years: int | None = dataclasses.field(default=None)
    quarters: int | None = dataclasses.field(default=None)
    months: int | None = dataclasses.field(default=None)
    weeks: int | None = dataclasses.field(default=None)
    days: int | None = dataclasses.field(default=None)
    hours: int | None = dataclasses.field(default=None)
    minutes: int | None = dataclasses.field(default=None)
    seconds: int | None = dataclasses.field(default=None)
    milliseconds: int | None = dataclasses.field(default=None)


class Moment(NoSSRComponent):
    """The Moment component."""

    tag: str | None = "Moment"
    is_default = True
    library: str | None = "react-moment@1.1.3"
    lib_dependencies: list[str] = ["moment@2.30.1"]

    # How often the date update (how often time update / 0 to disable).
    interval: Var[int]

    # Formats the date according to the given format string.
    format: Var[str]

    # When formatting duration time, the largest-magnitude tokens are automatically trimmed when they have no value.
    trim: Var[bool]

    #  Use the parse attribute to tell moment how to parse the given date when non-standard.
    parse: Var[str]

    # Add a delta to the base date (keys are "years", "quarters", "months", "weeks", "days", "hours", "minutes", "seconds")
    add: Var[MomentDelta]

    # Subtract a delta to the base date (keys are "years", "quarters", "months", "weeks", "days", "hours", "minutes", "seconds")
    subtract: Var[MomentDelta]

    # Displays the date as the time from now, e.g. "5 minutes ago".
    from_now: Var[bool]

    # Setting fromNowDuring will display the relative time as with fromNow but just during its value in milliseconds, after that format will be used instead.
    from_now_during: Var[int]

    # Similar to fromNow, but gives the opposite interval.
    to_now: Var[bool]

    # Adds a title attribute to the element with the complete date.
    with_title: Var[bool]

    # How the title date is formatted when using the withTitle attribute.
    title_format: Var[str]

    # Show the different between this date and the rendered child.
    diff: Var[str]

    # Display the diff as decimal.
    decimal: Var[bool]

    # Display the diff in given unit.
    unit: Var[str]

    # Shows the duration (elapsed time) between two dates. duration property should be behind date property time-wise.
    duration: Var[str]

    # The date to display (also work if passed as children).
    date: Var[str | datetime | date | time | timedelta]

    # Shows the duration (elapsed time) between now and the provided datetime.
    duration_from_now: Var[bool]

    # Tells Moment to parse the given date value as a unix timestamp.
    unix: Var[bool]

    # Outputs the result in local time.
    local: Var[bool]

    # Display the date in the given timezone.
    tz: Var[str]

    # The locale to use when rendering.
    locale: Var[str]

    # Fires when the date changes.
    on_change: EventHandler[passthrough_event_spec(str)]

    def add_imports(self) -> ImportDict:
        """Add the imports for the Moment component.

        Returns:
            The import dict for the component.
        """
        imports = {}

        if isinstance(self.locale, LiteralVar):
            imports[""] = f"moment/locale/{self.locale._var_value}"
        elif self.locale is not None:
            # If the user is using a variable for the locale, we can't know the
            # value at compile time so import all locales available.
            imports[""] = "moment/min/locales"
        if self.tz is not None:
            imports["moment-timezone"] = ""

        return imports
