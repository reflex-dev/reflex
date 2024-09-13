"""Moment component for humanized date rendering."""

import dataclasses
from typing import List, Optional

from reflex.components.component import Component, NoSSRComponent
from reflex.event import EventHandler
from reflex.utils.imports import ImportDict
from reflex.vars.base import Var


@dataclasses.dataclass(frozen=True)
class MomentDelta:
    """A delta used for add/subtract prop in Moment."""

    years: Optional[int] = dataclasses.field(default=None)
    quarters: Optional[int] = dataclasses.field(default=None)
    months: Optional[int] = dataclasses.field(default=None)
    weeks: Optional[int] = dataclasses.field(default=None)
    days: Optional[int] = dataclasses.field(default=None)
    hours: Optional[int] = dataclasses.field(default=None)
    minutess: Optional[int] = dataclasses.field(default=None)
    seconds: Optional[int] = dataclasses.field(default=None)
    milliseconds: Optional[int] = dataclasses.field(default=None)


class Moment(NoSSRComponent):
    """The Moment component."""

    tag: str = "Moment"
    is_default = True
    library: str = "react-moment"
    lib_dependencies: List[str] = ["moment"]

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
    date: Var[str]

    # Shows the duration (elapsed time) between now and the provided datetime.
    duration_from_now: Var[bool]

    # Tells Moment to parse the given date value as a unix timestamp.
    unix: Var[bool]

    # Outputs the result in local time.
    local: Var[bool]

    # Display the date in the given timezone.
    tz: Var[str]

    # Fires when the date changes.
    on_change: EventHandler[lambda date: [date]]

    def add_imports(self) -> ImportDict:
        """Add the imports for the Moment component.

        Returns:
            The import dict for the component.
        """
        if self.tz is not None:
            return {"moment-timezone": ""}
        return {}

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a Moment component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The Moment Component.
        """
        comp = super().create(*children, **props)
        if "tz" in props:
            comp.lib_dependencies.append("moment-timezone")
        return comp
