import reflex as rx
from azure_auth.auth.core import State as SsoState


@rx.page(route="/callback", on_load=SsoState.callback)
def callback() -> rx.Component:
    return rx.container()


@rx.page(route="/logout", on_load=SsoState.logout)
def logout() -> rx.Component:
    return rx.container("Logged out")


@rx.page(route="/", on_load=SsoState.require_auth)
def home() -> rx.Component:
    return rx.container(rx.cond(SsoState.check_auth, auth_view(), unauth_view()))


def auth_view() -> rx.Component:
    return rx.vstack(
        rx.text(f"Hello {SsoState.token['name']}"),
        rx.button("logout", on_click=SsoState.logout),
    )


def unauth_view() -> rx.Component:
    return rx.text("Unauthorized, redirected...")
