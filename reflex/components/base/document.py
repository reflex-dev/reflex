"""Document components."""

from reflex.components.component import Component


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


class Scripts(ReactRouterLib):
    """The document main scripts."""

    tag = "Scripts"
