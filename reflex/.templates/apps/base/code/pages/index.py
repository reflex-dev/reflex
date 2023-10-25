"""The home page of the app."""

import reflex as rx

from code.pages.template import template


@template(route="/")
def index() -> rx.Component:
    """The home page.

    Returns:
        The UI for the home page.
    """
    return rx.fragment(
        rx.heading("Home", font_size="3em"),
        rx.text("Welcome to Reflex!"),
        rx.text("You can use this template to get started with Reflex."),
    )
