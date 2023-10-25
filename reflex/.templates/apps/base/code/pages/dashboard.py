"""The dashboard page for the template."""
import reflex as rx

from code.pages.template import template


@template(route="/dashboard")
def dashboard() -> rx.Component:
    """The dashboard page.

    Returns:
        The UI for the dashboard page.
    """
    return rx.fragment(
        rx.heading("Dashboard", font_size="3em"),
        rx.text("Welcome to Reflex!"),
        rx.text("You can use this template to get started with Reflex."),
    )
