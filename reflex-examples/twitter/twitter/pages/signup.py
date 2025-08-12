"""Sign up page. Uses auth_layout to render UI shared with the login page."""

import reflex as rx
from twitter.layouts import auth_layout
from twitter.state.auth import AuthState


def signup():
    """The sign up page."""
    return auth_layout(
        rx.box(
            rx.vstack(
                rx.input(
                    placeholder="Username",
                    on_blur=AuthState.set_username,
                    size="3",
                ),
                rx.input(
                    type="password",
                    placeholder="Password",
                    on_blur=AuthState.set_password,
                    size="3",
                ),
                rx.input(
                    type="password",
                    placeholder="Confirm password",
                    on_blur=AuthState.set_confirm_password,
                    size="3",
                ),
                rx.button(
                    "Sign up",
                    on_click=AuthState.signup,
                    size="3",
                    width="6em",
                ),
                spacing="4",
            ),
            align_items="left",
            background="white",
            border="1px solid #eaeaea",
            padding="16px",
            width="400px",
            border_radius="8px",
        ),
        rx.text(
            "Already have an account? ",
            rx.link("Sign in here.", href="/"),
            color="gray",
        ),
    )
