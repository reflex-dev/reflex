"""Module for the StrictMode component."""

from reflex_core.components.component import Component


class StrictMode(Component):
    """A React strict mode component to enable strict mode for its children."""

    library = "react"
    tag = "StrictMode"
