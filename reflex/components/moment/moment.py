"""Moment component for humanized date rendering."""

from typing import List, Optional

from reflex.base import Base
from reflex.components.component import Component, NoSSRComponent
from reflex.event import EventHandler
from reflex.ivars.base import ImmutableVar
from reflex.utils.imports import ImportDict


class MomentDelta(Base):
    """A delta used for add/subtract prop in Moment."""

    years: Optional[int]
    quarters: Optional[int]
    months: Optional[int]
    weeks: Optional[int]
    days: Optional[int]
    hours: Optional[int]
    minutess: Optional[int]
    seconds: Optional[int]
    milliseconds: Optional[int]


class Moment(NoSSRComponent):
    """The Moment component."""

    tag: str = "Moment"
    is_default = True
    library: str = "react-moment"
    lib_dependencies: List[str] = ["moment"]

    # How often the date update (how often time update / 0 to disable).
    interval: ImmutableVar[int]

    # Formats the date according to the given format string.
    format: ImmutableVar[str]

    # When formatting duration time, the largest-magnitude tokens are automatically trimmed when they have no value.
    trim: ImmutableVar[bool]

    #  Use the parse attribute to tell moment how to parse the given date when non-standard.
    parse: ImmutableVar[str]

    # Add a delta to the base date (keys are "years", "quarters", "months", "weeks", "days", "hours", "minutes", "seconds")
    add: ImmutableVar[MomentDelta]

    # Subtract a delta to the base date (keys are "years", "quarters", "months", "weeks", "days", "hours", "minutes", "seconds")
    subtract: ImmutableVar[MomentDelta]

    # Displays the date as the time from now, e.g. "5 minutes ago".
    from_now: ImmutableVar[bool]

    # Setting fromNowDuring will display the relative time as with fromNow but just during its value in milliseconds, after that format will be used instead.
    from_now_during: ImmutableVar[int]

    # Similar to fromNow, but gives the opposite interval.
    to_now: ImmutableVar[bool]

    # Adds a title attribute to the element with the complete date.
    with_title: ImmutableVar[bool]

    # How the title date is formatted when using the withTitle attribute.
    title_format: ImmutableVar[str]

    # Show the different between this date and the rendered child.
    diff: ImmutableVar[str]

    # Display the diff as decimal.
    decimal: ImmutableVar[bool]

    # Display the diff in given unit.
    unit: ImmutableVar[str]

    # Shows the duration (elapsed time) between two dates. duration property should be behind date property time-wise.
    duration: ImmutableVar[str]

    # The date to display (also work if passed as children).
    date: ImmutableVar[str]

    # Shows the duration (elapsed time) between now and the provided datetime.
    duration_from_now: ImmutableVar[bool]

    # Tells Moment to parse the given date value as a unix timestamp.
    unix: ImmutableVar[bool]

    # Outputs the result in local time.
    local: ImmutableVar[bool]

    # Display the date in the given timezone.
    tz: ImmutableVar[str]

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
