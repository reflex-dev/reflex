"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from .pages import home, login, signup
from .state.base import State


app = rx.App()
app.add_page(login)
app.add_page(signup)
app.add_page(home, route="/", on_load=State.check_login())
