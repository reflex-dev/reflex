"""The settings page for the template."""

import reflex as rx

from code.pages.template import template


@rx.page("/settings")
@template
def settings() -> rx.Component:
    """The settings page.

    Returns:
        The UI for the settings page.
    """
    return rx.fragment(
        rx.heading("Settings", font_size="3em"),
        rx.text("Welcome to Reflex!"),
        rx.text("You can use this template to get started with Reflex."),
    )
