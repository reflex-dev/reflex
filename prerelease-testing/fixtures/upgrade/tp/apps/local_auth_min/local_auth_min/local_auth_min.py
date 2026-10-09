"""Second, minimal app that also uses reflex-local-auth (for the two-apps-in-one-process AppHarness test)."""

import reflex as rx
import reflex_local_auth
from reflex.model import migrate


class MinState(reflex_local_auth.LocalAuthState):
    secret: str = ""

    @rx.event
    def reveal(self):
        self.secret = f"min-secret for {self.authenticated_user.username}" if self.is_authenticated else "denied"


@rx.page(route="/")
def index() -> rx.Component:
    return rx.vstack(rx.heading("local_auth_min home"), rx.link("Gated", href="/gated"), rx.link("Login", href="/login"))


@rx.page(route="/gated", on_load=MinState.reveal)
@reflex_local_auth.require_login
def gated() -> rx.Component:
    return rx.vstack(rx.heading("Gated page"), rx.text(MinState.secret, id="min_secret"))


app = rx.App()
app.add_page(reflex_local_auth.pages.login_page, route=reflex_local_auth.routes.LOGIN_ROUTE, title="Login")
app.add_page(reflex_local_auth.pages.register_page, route=reflex_local_auth.routes.REGISTER_ROUTE, title="Register")
migrate()
