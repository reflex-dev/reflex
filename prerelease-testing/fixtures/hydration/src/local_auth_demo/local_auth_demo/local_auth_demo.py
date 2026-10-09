"""Main app module to demo local authentication."""

import os as _os_guard

import reflex as rx
import reflex_local_auth

assert f"/envs/{_os_guard.environ['RVH_VENV']}/" in rx.__file__, (_os_guard.environ.get("RVH_VENV"), rx.__file__)
from reflex.model import migrate

from . import custom_user_info as custom_user_info


def links() -> rx.Component:
    """Render the links for the demo."""
    return rx.fragment(
        rx.link("Home", href="/"),
        rx.link("Need 2 Login", href="/need2login"),
        rx.link("Protected Page", href="/protected"),
        rx.link("Custom Register", href="/custom-register"),
        rx.link("User Info", href="/user-info"),
        rx.cond(
            reflex_local_auth.LocalAuthState.is_authenticated,
            rx.link(
                "Logout",
                href="/",
                on_click=reflex_local_auth.LocalAuthState.do_logout,
            ),
            rx.link("Login", href=reflex_local_auth.routes.LOGIN_ROUTE),
        ),
    )


@rx.page()
def index() -> rx.Component:
    """Render the index page.

    Returns:
        A reflex component.
    """
    return rx.fragment(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Welcome to my homepage!", font_size="2em"),
            links(),
            spacing="2",
            padding_top="10%",
            align="center",
        ),
    )


@rx.page()
@reflex_local_auth.require_login
def need2login():
    return rx.vstack(
        rx.heading(
            "Accessing this page will redirect to the login page if not authenticated."
        ),
        links(),
        spacing="2",
        padding_top="10%",
        align="center",
    )


class ProtectedState(reflex_local_auth.LocalAuthState):
    data: str

    @rx.event
    def on_load(self):
        if not self.is_authenticated:
            return reflex_local_auth.LoginState.redir
        self.data = f"This is truly private data for {self.authenticated_user.username}"

    @rx.event
    def do_logout(self):
        self.data = ""
        return reflex_local_auth.LocalAuthState.do_logout


@rx.page(on_load=ProtectedState.on_load)
@reflex_local_auth.require_login
def protected():
    return rx.vstack(
        rx.heading(ProtectedState.data),
        links(),
        spacing="2",
        padding_top="10%",
        align="center",
    )


app = rx.App()
app.add_page(
    reflex_local_auth.pages.login_page,
    route=reflex_local_auth.routes.LOGIN_ROUTE,
    title="Login",
)
app.add_page(
    reflex_local_auth.pages.register_page,
    route=reflex_local_auth.routes.REGISTER_ROUTE,
    title="Register",
)

# Create the database if it does not exist (hosting service does not migrate automatically)
migrate()

# thirdparty cluster: extra test pages (not upstream)
import os as _os  # noqa: E402

if _os.environ.get("TP_EXTRA", "1") == "1":
    from . import tp_extra as tp_extra  # noqa: E402
