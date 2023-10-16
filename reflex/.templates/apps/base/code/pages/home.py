"""The home page of the app."""
import reflex as rx

from ..styles import *


def home_page() -> rx.Component:
    """The UI for the home page.

    Returns:
        rx.Component: The UI for the home page.
    """
    return rx.box(
        rx.vstack(
            rx.heading(
                "Home",
                size="3em",
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
