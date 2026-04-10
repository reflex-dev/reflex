"""Moment component for humanized date rendering."""

from __future__ import annotations

import dataclasses
import datetime

from reflex_base.components.component import NoSSRComponent, field
from reflex_base.event import EventHandler, passthrough_event_spec
from reflex_base.utils.imports import ImportDict
from reflex_base.vars.base import LiteralVar, Var


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
    library: str | None = "react-moment@1.2.2"
    lib_dependencies: list[str] = ["moment@2.30.1"]

    interval: Var[int] = field(
        doc="How often the date update (how often time update / 0 to disable)."
    )

    format: Var[str] = field(
        doc="Formats the date according to the given format string."
    )

    trim: Var[bool] = field(
        doc="When formatting duration time, the largest-magnitude tokens are automatically trimmed when they have no value."
    )

    parse: Var[str] = field(
        doc=" Use the parse attribute to tell moment how to parse the given date when non-standard."
    )

    add: Var[MomentDelta] = field(
        doc='Add a delta to the base date (keys are "years", "quarters", "months", "weeks", "days", "hours", "minutes", "seconds")'
    )

    subtract: Var[MomentDelta] = field(
        doc='Subtract a delta to the base date (keys are "years", "quarters", "months", "weeks", "days", "hours", "minutes", "seconds")'
    )

    from_now: Var[bool] = field(
        doc='Displays the date as the time from now, e.g. "5 minutes ago".'
    )

    from_now_short: Var[bool] = field(
        doc='Displays the relative time in a short format using abbreviated units (e.g., "1h", "2d", "3mo", "1y" instead of "1 hour ago", "2 days ago", etc.).'
    )

    from_now_during: Var[int] = field(
        doc="Setting fromNowDuring will display the relative time as with fromNow but just during its value in milliseconds, after that format will be used instead."
    )

    to_now: Var[bool] = field(
        doc="Similar to fromNow, but gives the opposite interval."
    )

    with_title: Var[bool] = field(
        doc="Adds a title attribute to the element with the complete date."
    )

    title_format: Var[str] = field(
        doc="How the title date is formatted when using the withTitle attribute."
    )

    diff: Var[str] = field(
        doc="Show the different between this date and the rendered child."
    )

    decimal: Var[bool] = field(doc="Display the diff as decimal.")

    unit: Var[str] = field(doc="Display the diff in given unit.")

    duration: Var[str] = field(
        doc="Shows the duration (elapsed time) between two dates. duration property should be behind date property time-wise."
    )

    date: Var[
        str | datetime.datetime | datetime.date | datetime.time | datetime.timedelta
    ] = field(doc="The date to display (also work if passed as children).")

    duration_from_now: Var[bool] = field(
        doc="Shows the duration (elapsed time) between now and the provided datetime."
    )

    unix: Var[bool] = field(
        doc="Tells Moment to parse the given date value as a unix timestamp."
    )

    local: Var[bool] = field(doc="Outputs the result in local time.")

    tz: Var[str] = field(doc="Display the date in the given timezone.")

    locale: Var[str] = field(doc="The locale to use when rendering.")

    on_change: EventHandler[passthrough_event_spec(str)] = field(
        doc="Fires when the date changes."
    )

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
