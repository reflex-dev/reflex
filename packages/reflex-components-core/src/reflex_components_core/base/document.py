"""Document components."""

from reflex_base.components.component import Component


class ReactRouterLib(Component):
    """Root document components."""

    library = "react-router"


class Meta(ReactRouterLib):
    """The document meta tags."""

    tag = "Meta"


class Links(ReactRouterLib):
    """The document link tags."""

    tag = "Links"


class ScrollRestoration(ReactRouterLib):
    """The document scroll restoration."""

    tag = "ScrollRestoration"


class Outlet(ReactRouterLib):
    """The document outlet."""

    tag = "Outlet"


class Scripts(Component):
    """The document main scripts.

    Renders react-router's scripts, started after the first paint on a
    prerendered page.
    """

    library = "$/utils/scripts"

    tag = "Scripts"
