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


RAN: list[str] = []


class Vault(rx.State):
    """Protected handlers (default auth=True)."""

    @rxe.event
    async def secret_action(self) -> str:
        """Protected: record a run and return a secret.

        Returns:
            The secret.
        """
        RAN.append("secret_action")
        return "secret-value"

    @rxe.event(auth=False)
    async def public_action(self) -> str:
        """Public control: return a value.

        Returns:
            The value.
        """
        return "public-value"


class Pub(rx.State):
    """Public state awaiting the protected handler."""

    result: str = rxe.field("unset", auth=False)
    ran: int = rxe.field(-1, auth=False)

    @rxe.event(auth=False)
    async def call_protected(self):
        """Await the protected handler from an anonymous (or signed-in) session."""
        r = await Vault.secret_action()
        self.result = repr(r)
        self.ran = len(RAN)

    @rxe.event(auth=False)
    async def call_public(self):
        """Positive control: await a public handler."""
        self.result = repr(await Vault.public_action())

    @rxe.event(auth=False)
    def read_ran(self):
        """Read the run counter."""
        self.ran = len(RAN)


@rxe.page(route="/await", auth=False)
def await_page() -> rx.Component:
    """Await-a-protected-handler probe.

    Returns:
        The probe page.
    """
    return rx.vstack(
        rx.button("call", id="call", on_click=Pub.call_protected),
        rx.button("direct", id="direct", on_click=Vault.secret_action),
        rx.button("read", id="readran", on_click=Pub.read_ran),
        rx.button("public", id="public", on_click=Pub.call_public),
        rx.text(Pub.result, id="result"),
        rx.text(Pub.ran, id="ran"),
    )


app = rxe.App()
