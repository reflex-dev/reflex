"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx
from reflex.components.radix.themes import theme

from .pages import home, login, signup
from .state.base import State


app = rx.App(
    theme=theme(
        appearance="light", has_background=True, radius="large", accent_color="teal"
    )
)
app.add_page(login)
app.add_page(signup)
app.add_page(home, route="/", on_load=State.check_login())
