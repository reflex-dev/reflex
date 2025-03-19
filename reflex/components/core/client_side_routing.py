"""Handle dynamic routes in static exports via client-side routing.

Works with /utils/client_side_routing.js to handle the redirect and state.

When the user hits a 404 accessing a route, redirect them to the same page,
setting a reactive state var "routeNotFound" to true if the redirect fails.  The
`wait_for_client_redirect` function will render the component only after
routeNotFound becomes true.
"""

from __future__ import annotations

from reflex import constants
from reflex.components.component import Component
from reflex.components.core.cond import cond
from reflex.vars.base import Var

route_not_found: Var = Var(_js_expr=constants.ROUTE_NOT_FOUND)


class ClientSideRouting(Component):
    """The client-side routing component."""

    library = "$/utils/client_side_routing"
    tag = "useClientSideRouting"

    def add_hooks(self) -> list[str | Var]:
        """Get the hooks to render.

        Returns:
            The useClientSideRouting hook.
        """
        return [f"const {constants.ROUTE_NOT_FOUND} = {self.tag}()"]

    def render(self) -> str:
        """Render the component.

        Returns:
            Empty string, because this component is only used for its hooks.
        """
        return ""


def wait_for_client_redirect(component: Component) -> Component:
    """Wait for a redirect to occur before rendering a component.

    This prevents the 404 page from flashing while the redirect is happening.

    Args:
        component: The component to render after the redirect.

    Returns:
        The conditionally rendered component.
    """
    return cond(
        route_not_found,
        component,
        ClientSideRouting.create(),
    )


def default_404_page() -> Component:
    """Render the default 404 page.

    Returns:
        The 404 page component.
    """
    import reflex as rx

    return rx.el.span("404: Page not found")
