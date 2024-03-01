"""Moment component for humanized date rendering."""
from typing import Any, Dict, List, Optional

from reflex.base import Base
from reflex.components.component import Component, NoSSRComponent
from reflex.utils import imports
from reflex.vars import Var


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
    is_default: bool = True
    library: str = "react-moment"
    lib_dependencies: List[str] = ["moment"]

    # How often the date update (how often time update / 0 to disable).
    interval: Optional[Var[int]] = None

    # Formats the date according to the given format string.
    format: Optional[Var[str]] = None

    # When formatting duration time, the largest-magnitude tokens are automatically trimmed when they have no value.
    trim: Optional[Var[bool]] = None

    #  Use the parse attribute to tell moment how to parse the given date when non-standard.
    parse: Optional[Var[str]] = None

    # Add a delta to the base date (keys are "years", "quarters", "months", "weeks", "days", "hours", "minutes", "seconds")
    add: Optional[Var[MomentDelta]] = None

    # Subtract a delta to the base date (keys are "years", "quarters", "months", "weeks", "days", "hours", "minutes", "seconds")
    subtract: Optional[Var[MomentDelta]] = None

    # Displays the date as the time from now, e.g. "5 minutes ago".
    from_now: Optional[Var[bool]] = None

    # Setting fromNowDuring will display the relative time as with fromNow but just during its value in milliseconds, after that format will be used instead.
    from_now_during: Optional[Var[int]] = None

    # Similar to fromNow, but gives the opposite interval.
    to_now: Optional[Var[bool]] = None

    # Adds a title attribute to the element with the complete date.
    with_title: Optional[Var[bool]] = None

    # How the title date is formatted when using the withTitle attribute.
    title_format: Optional[Var[str]] = None

    # Show the different between this date and the rendered child.
    diff: Optional[Var[str]] = None

    # Display the diff as decimal.
    decimal: Optional[Var[bool]] = None

    # Display the diff in given unit.
    unit: Optional[Var[str]] = None

    # Shows the duration (elapsed time) between two dates. duration property should be behind date property time-wise.
    duration: Optional[Var[str]] = None

    # The date to display (also work if passed as children).
    date: Optional[Var[str]] = None

    # Shows the duration (elapsed time) between now and the provided datetime.
    duration_from_now: Optional[Var[bool]] = None

    # Tells Moment to parse the given date value as a unix timestamp.
    unix: Optional[Var[bool]] = None

    # Outputs the result in local time.
    local: Optional[Var[bool]] = None

    # Display the date in the given timezone.
    tz: Optional[Var[str]] = None

    def _get_imports(self) -> imports.ImportDict:
        merged_imports = super()._get_imports()
        if self.tz is not None:
            merged_imports = imports.merge_imports(
                merged_imports,
                {"moment-timezone": {imports.ImportVar(tag="")}},
            )
        return merged_imports

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_change": lambda date: [date],
        }

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
