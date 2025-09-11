"""Helmet component module."""

from reflex.components.component import Component


class Helmet(Component):
    """A helmet component."""

    library = "@dr.pogodin/react-helmet@3.0.4"

    tag = "Helmet"


class HelmetProvider(Component):
    """A helmet provider component."""

    library = "@dr.pogodin/react-helmet@3.0.4"

    tag = "HelmetProvider"


helmet = Helmet.create
helmet_provider = HelmetProvider.create
