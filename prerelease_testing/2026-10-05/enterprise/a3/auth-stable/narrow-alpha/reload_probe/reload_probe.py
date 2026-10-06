"""Reproduce protected async-var hydration with core public State fields."""

import reflex as rx
import reflex_enterprise as rxe
from reflex_enterprise.auth import AuthUserState
from reflex_enterprise.auth.types import VarAuthContext


class OrgState(rx.State):
    """Provide an ordinary core field for the awaited authorization check."""

    admin_group: str = "admins"


async def is_admin(ctx: VarAuthContext) -> bool:
    """Authorize an admin using an awaited sibling State lookup.

    Args:
        ctx: The enterprise variable authorization context.

    Returns:
        Whether the user's claims contain the configured admin group.
    """
    org = await ctx.auth_user_state.get_state(OrgState)
    return org.admin_group in (ctx.auth_user_state.userinfo.get("groups") or [])


class ProbeState(rx.State):
    """Expose sync and async protected getters without enterprise fields."""

    secret: str = "initial-secret"

    @rxe.var(initial_value="sync-placeholder")
    def sync_view(self) -> str:
        """Return the protected core value.

        Returns:
            The core secret prefixed for a visible synchronization assertion.
        """
        return "computed:" + self.secret

    @rxe.var(auth=is_admin, initial_value="async-admin-placeholder")
    async def async_view(self) -> str:
        """Return the protected async result.

        Returns:
            A fixed marker once the awaited authorization check succeeds.
        """
        return "async-admin-data"


def surfaces() -> rx.Component:
    """Render the markers used to compare navigation and full reload.

    Returns:
        The shared diagnostic surface.
    """
    return rx.vstack(
        rx.text(ProbeState.secret, id="secret"),
        rx.text(ProbeState.sync_view, id="sync-view"),
        rx.text(ProbeState.async_view, id="async-view"),
        rx.text(AuthUserState.name, id="user-name"),
    )


@rxe.page(route="/", auth=False)
def index() -> rx.Component:
    """Render a public page containing protected computed vars.

    Returns:
        The diagnostic surface.
    """
    return surfaces()


@rxe.page(route="/dashboard")
def dashboard() -> rx.Component:
    """Trigger the normal OIDC login flow.

    Returns:
        The authenticated diagnostic surface.
    """
    return surfaces()


app = rxe.App()
