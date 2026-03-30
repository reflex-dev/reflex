"""Helmet component module."""

from reflex_core.components.component import Component


class Helmet(Component):
    """A helmet component."""

    library = "react-helmet@6.1.0"

    tag = "Helmet"


helmet = Helmet.create
