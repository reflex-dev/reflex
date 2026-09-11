"""Minimal repro: prod trailing-slash redirect vs router.url.path vs reflex-local-auth login."""

import reflex as rx
import reflex_local_auth

assert "/envs/verify2_up_lorem_form_1" in rx.__file__, rx.__file__


class Probe(rx.State):
    """Expose the framework's own view of the current route."""

    @rx.var
    def router_path(self) -> str:
        return self.router.url.path

    @rx.var
    def route_id(self) -> str:
        return self.router.route_id

    @rx.var
    def route_id_matches(self) -> str:
        return (
            "MATCH"
            if self.router.route_id == reflex_local_auth.routes.LOGIN_ROUTE
            else "MISMATCH"
        )

    @rx.var
    def login_route_matches(self) -> str:
        return (
            "MATCH"
            if self.router.url.path == reflex_local_auth.routes.LOGIN_ROUTE
            else "MISMATCH"
        )


def probe_block(name: str) -> rx.Component:
    return rx.vstack(
        rx.heading(name, id="heading"),
        rx.text(Probe.router_path, id="routerpath"),
        rx.text(Probe.login_route_matches, id="matches"),
        rx.text(Probe.route_id, id="routeid"),
        rx.text(Probe.route_id_matches, id="routeidmatches"),
        rx.cond(
            reflex_local_auth.LocalAuthState.is_authenticated,
            rx.text("AUTHED", id="authstatus"),
            rx.text("ANON", id="authstatus"),
        ),
        rx.link("go login", href="/login", id="gologin"),
    )


def index() -> rx.Component:
    return probe_block("index")


def login() -> rx.Component:
    return rx.vstack(probe_block("loginwrap"), reflex_local_auth.pages.login_page())


@reflex_local_auth.require_login
def protected() -> rx.Component:
    return probe_block("protected")


app = rx.App()
app.add_page(index, route="/")
app.add_page(login, route=reflex_local_auth.routes.LOGIN_ROUTE, title="Login")
app.add_page(
    reflex_local_auth.pages.register_page,
    route=reflex_local_auth.routes.REGISTER_ROUTE,
    title="Register",
)
app.add_page(protected, route="/protected", title="Protected")

rx.model.Model.create_all()
