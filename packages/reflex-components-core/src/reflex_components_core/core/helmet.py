"""Helmet component module."""

from reflex_base.components.component import Component
from reflex_base.vars.base import Var


class Helmet(Component):
    """A helmet component."""

    library = "react-helmet@6.1.0"

    tag = "Helmet"

    # Whether to batch client-side head updates via requestAnimationFrame.
    defer: Var[bool]


helmet = Helmet.create
