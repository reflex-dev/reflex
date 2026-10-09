"""reflex-azure-auth 0.1.2 against the local mock OIDC IdP (AZURE_ISSUER_URI=http://localhost:8638).

Its on_load handlers read the router (reflex#7360 dropped router_data from on_load events):
  /authorization-code/callback  on_load=AzureAuthState.auth_callback   -> self.router.url.query_parameters (code, state), _redirect_uri()
  /protected                    on_load=Guard.check -> returns AzureAuthState.redirect_to_login (backend chain) -> self._redirect_to_url = self.router.url
"""

import reflex as rx
import reflex_enterprise as rxe
from reflex_azure_auth import AzureAuthState, azure_login_button, register_auth_endpoints


class Guard(rx.State):
    """Protected-page on_load: start the login flow when there is no valid token."""

    loads: list[str] = []

    @rx.event
    async def check(self):
        """Record the router view; redirect to login when anonymous."""
        self.loads.append(f"{self.router.url.path}?{self.router.url.query}")
        az = await self.get_state(AzureAuthState)
        if not await az._validate_tokens():
            return AzureAuthState.redirect_to_login


def index() -> rx.Component:
    return rx.vstack(
        rx.heading("az home"),
        rx.text("has_token=", rx.text.span(AzureAuthState.access_token != "", id="has_token")),
        rx.text("error=", rx.text.span(AzureAuthState.error_message, id="error")),
        azure_login_button(),
        rx.link("protected", href="/protected?x=nav", id="nav-protected"),
    )


def protected() -> rx.Component:
    return rx.vstack(
        rx.heading("az protected"),
        rx.text("has_token=", rx.text.span(AzureAuthState.access_token != "", id="has_token")),
        rx.text("loads=", rx.text.span(Guard.loads.join(" | "), id="loads")),
        rx.text("error=", rx.text.span(AzureAuthState.error_message, id="error")),
    )


app = rxe.App()
app.add_page(index, route="/")
app.add_page(protected, route="/protected", on_load=Guard.check)
register_auth_endpoints(app)
