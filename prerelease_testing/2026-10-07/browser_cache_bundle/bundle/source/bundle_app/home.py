"""Public lightweight landing page."""

import reflex as rx
from .common import shell


def index() -> rx.Component:
    """Build the landing page.

    Returns:
        Static welcome content with no heavy widgets.
    """
    return shell(
        "Workspace home",
        rx.text("Review open orders, inspect trends, and edit the product catalog."),
        rx.link("Open dashboard", href="/dashboard", id="open-dashboard"),
    )
