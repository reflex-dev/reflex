"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from azure_auth.pages import callback, home, logout  # noqa: F401


class State(rx.State):
    """The app state."""

    ...


app = rx.App()
