"""Handle dynamic routes in static exports via client-side routing.

Works with /utils/client_side_routing.js to handle the redirect and state.

When the user hits a 404 accessing a route, redirect them to the same page,
setting set a top-level reactive state var "routeNotFound" to true if the
redirect fails.  The `wait_for_client_redirect` function will render the
component only after routeNotFound becomes true.
"""
from __future__ import annotations

from reflex import constants

from ...vars import Var
from ..component import Component
from ..layout.cond import Cond

route_not_found = Var.create_safe(constants.ROUTE_NOT_FOUND)


def wait_for_client_redirect(component) -> Component:
    """Wait for a redirect to occur before rendering a component.

    This prevents the 404 page from flashing while the redirect is happening.

    Args:
        component: The component to render after the redirect.

    Returns:
        The conditionally rendered component.
    """
    return Cond.create(
        cond=route_not_found,
        comp1=component,
        comp2=None,
    )


class Default404Page(Component):
    """The NextJS default 404 page."""

    library = "next/error"
    tag = "Error"
    is_default = True

    status_code: Var[int] = 404  # type: ignore
