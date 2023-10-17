"""Moment component for humanized date rendering."""

from typing import Any, Dict

from reflex.components.component import NoSSRComponent
from reflex.vars import Var


class Moment(NoSSRComponent):
    """The Moment component."""

    tag: str = "Moment"
    is_default = True
    library: str = "react-moment"
    lib_dependencies: list[str] = ["moment"]

    # interval (how often time update / 0 to disable)
    interval: Var[int]

    # format string
    format: Var[str]

    trim: Var[bool]

    to_now: Var[bool]

    to: Var[str]

    with_title: Var[bool]

    title_format: Var[str]

    diff: Var[str]

    decimal: Var[bool]

    unit: Var[str]

    duration: Var[str]

    date: Var[str]

    unix: Var[bool]

    local: Var[bool]

    tz: Var[str]

    # duration from now
    duration_from_now: Var[bool]

    # humanized time from now
    from_now: Var[bool]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_change": lambda date: [date],
        }
