"""The settings page."""

from code.templates import template

import reflex as rx


@template(route="/settings", title="Settings")
def settings() -> rx.Component:
    """The settings page.

    Returns:
        The UI for the settings page.
    """
    return rx.chakra.vstack(
        rx.chakra.heading("Settings", font_size="3em"),
        rx.chakra.text("Welcome to Reflex!"),
        rx.chakra.text(
            "You can edit this page in ",
            rx.chakra.code("{your_app}/pages/settings.py"),
        ),
    )
