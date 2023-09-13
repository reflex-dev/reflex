"""Moment component for humanized date rendering."""

from reflex.components.component import Component
from reflex.vars import Var


class Moment(Component):
    """The Moment component."""

    tag: str = "Moment"
    library: str = "react-moment"
    lib_dependencies: list[str] = ["moment"]

    is_default = True

    # interval (how often time update / 0 to disable)
    interval: Var[int]

    # format string
    format: Var[str]

    # duration from now
    durationFromNow: Var[bool]

    # humanized time from now
    fromNow: Var[bool]
