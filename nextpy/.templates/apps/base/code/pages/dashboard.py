"""The dashboard page."""
from code.templates import template

import nextpy as xt


@template(route="/dashboard", title="Dashboard")
def dashboard() -> xt.Component:
    """The dashboard page.

    Returns:
        The UI for the dashboard page.
    """
    return xt.vstack(
        xt.heading("Dashboard", font_size="3em"),
        xt.text("Welcome to Nextpy!"),
        xt.text(
            "You can edit this page in ",
            xt.code("{your_app}/pages/dashboard.py"),
        ),
    )
