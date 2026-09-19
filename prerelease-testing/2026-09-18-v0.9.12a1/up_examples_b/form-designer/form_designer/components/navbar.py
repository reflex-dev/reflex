import reflex as rx

import reflex_local_auth
from reflex_local_auth import LocalAuthState

from .. import routes


def navbar_menu() -> rx.Component:
    return rx.menu.root(
        rx.menu.trigger(rx.icon("menu", size=20), cursor="pointer"),
        rx.menu.content(
            rx.cond(
                LocalAuthState.is_authenticated,
                rx.fragment(
                    rx.hstack(
                        rx.avatar(
                            fallback=LocalAuthState.authenticated_user.username[0],
                            size="1",
                        ),
                        rx.text(
                            LocalAuthState.authenticated_user.username,
                        ),
                        margin="8px",
                    ),
                    rx.menu.separator(),
                ),
            ),
            rx.menu.item("Home", on_click=rx.redirect("/")),
            rx.menu.item("Forms", on_click=rx.redirect(routes.FORM_EDIT_NEW)),
            rx.cond(
                LocalAuthState.is_authenticated,
                rx.menu.item(
                    "Logout",
                    on_click=[
                        LocalAuthState.do_logout,
                        rx.redirect("/"),
                    ],
                ),
                rx.fragment(
                    rx.menu.item(
                        "Register",
                        on_click=rx.redirect(reflex_local_auth.routes.REGISTER_ROUTE),
                    ),
                    rx.menu.item(
                        "Login",
                        on_click=rx.redirect(reflex_local_auth.routes.LOGIN_ROUTE),
                    ),
                ),
            ),
            rx.menu.separator(),
            rx.hstack(
                rx.icon("sun", size=16),
                rx.switch(
                    checked=rx.style.color_mode != rx.style.LIGHT_COLOR_MODE,
                    on_change=rx.style.toggle_color_mode,
                    size="1",
                ),
                rx.icon("moon", size=16),
                margin="8px",
            ),
        ),
    )


def navbar(title_suffix: str | None = None) -> rx.Component:
    title = "Form Designer"
    if title_suffix is not None:
        title += f" - {title_suffix}"
    return rx.hstack(
        rx.heading(title),
        rx.spacer(),
        navbar_menu(),
        margin_y="12px",
        align="center",
    )
