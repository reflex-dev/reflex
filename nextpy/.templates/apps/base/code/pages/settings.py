"""The settings page."""

from code.templates import template

import nextpy as xt


@template(route="/settings", title="Settings")
def settings() -> xt.Component:
    """The settings page.

    Returns:
        The UI for the settings page.
    """
    return xt.vstack(
        xt.heading("Settings", font_size="3em"),
        xt.text("Welcome to Nextpy!"),
        xt.text(
            "You can edit this page in ",
            xt.code("{your_app}/pages/settings.py"),
        ),
    )
