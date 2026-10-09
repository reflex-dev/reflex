"""OIDC/profile compatibility checks independent of the rxe.field failure."""

import reflex_enterprise as rxe
from reflex_enterprise.auth import AuthUserState
from reflex_enterprise.auth.oidc.state import GenericOIDCAuthState

import reflex as rx


class ProfileState(rx.State):
    """Track protected actions and token refresh results."""

    message: str = "initial"
    refresh_result: str = ""

    @rxe.event
    async def reveal(self):
        """Resolve the current user's identity in a protected event."""
        user = await AuthUserState.current() or {}
        self.message = "revealed-" + user.get("sub", "")

    @rxe.event
    async def force_refresh(self):
        """Round-trip a refresh token through the local OIDC provider."""
        provider_cls = await AuthUserState.current_provider()
        assert provider_cls is not None
        provider = await self.get_state(provider_cls)
        token = await provider._refresh_access_token(None)
        self.refresh_result = "refreshed" if token else "failed"


@rxe.page(route="/", auth=False)
def index() -> rx.Component:
    """Render a public page with an action that requires login.

    Returns:
        The public action and navigation page.
    """
    return rx.vstack(
        rx.heading("Published enterprise auth test"),
        rx.cond(
            AuthUserState.sub,
            rx.text("Signed in", id="signed-in"),
            GenericOIDCAuthState.get_login_button(),
        ),
        rx.text(ProfileState.message, id="message"),
        rx.button("Reveal", on_click=ProfileState.reveal),
        rx.link("Protected profile", href="/profile"),
    )


@rxe.page(route="/profile")
def profile() -> rx.Component:
    """Render normalized OIDC profile vars and protected event results.

    Returns:
        The authenticated profile.
    """
    return rx.vstack(
        rx.heading("Profile"),
        rx.text(AuthUserState.name, id="name"),
        rx.text(AuthUserState.email, id="email"),
        rx.text(ProfileState.message, id="message"),
        rx.text(ProfileState.refresh_result, id="refresh-result"),
        rx.button("Reveal", on_click=ProfileState.reveal),
        rx.button("Refresh", on_click=ProfileState.force_refresh),
        rx.button("Logout", on_click=AuthUserState.logout),
    )


@rxe.page(route="/iframe", auth=False)
def iframe() -> rx.Component:
    """Embed the public app to exercise popup login.

    Returns:
        The page embedding the same app.
    """
    return rx.el.iframe(src="/", width="100%", height="700px")


app = rxe.App()
