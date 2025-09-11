"""Helmet component module."""

from reflex.components.component import Component


class Helmet(Component):
    """A helmet component."""

    library = "react-helmet-async@2.0.5"

    tag = "Helmet"


class HelmetProvider(Component):
    """A helmet provider component."""

    library = "react-helmet-async@2.0.5"

    tag = "HelmetProvider"


helmet = Helmet.create
helmet_provider = HelmetProvider.create
