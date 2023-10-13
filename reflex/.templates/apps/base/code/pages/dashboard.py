"""The dashboard page for the template."""
import reflex as rx
from ..styles import *


def dashboard_page():
    """The UI for the dashboard page."""
    return rx.box(
        rx.vstack(
            rx.heading(
                "Dashboard",
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
