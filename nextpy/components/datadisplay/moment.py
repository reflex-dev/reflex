"""Moment component for humanized date rendering."""

from typing import Any, Dict, List

from nextpy.components.component import Component, NoSSRComponent
from nextpy.utils import imports
from nextpy.core.vars import ImportVar, Var


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

    # NOT IMPLEMENTED :
    # add
    # substract

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

    def _get_imports(self) -> imports.ImportDict:
        merged_imports = super()._get_imports()
        if self.tz is not None:
            merged_imports = imports.merge_imports(
                merged_imports,
                {"moment-timezone": {ImportVar(tag="")}},
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
