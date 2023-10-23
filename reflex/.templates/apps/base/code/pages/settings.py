"""The settings page for the template."""
import reflex as rx

from ..styles import *


def settings_page() -> rx.Component:
    """The UI for the settings page.

    Returns:
        rx.Component: The UI for the settings page.
    """
    return rx.box(
        rx.vstack(
            rx.heading(
                "Settings",
                font_size="3em",
            ),
            rx.text(
                "Welcome to Reflex!",
            ),
            rx.text(
                "You can use this template to get started with Reflex.",
            ),
            style=template_content_style,
        ),
        style=template_page_style,
    )
