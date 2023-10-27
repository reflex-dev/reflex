"""The home page of the app."""

from code import styles
from code.templates import template

import reflex as rx


@template(route="/", title="Home", image="/logo.svg")
def index() -> rx.Component:
    """The home page.

    Returns:
        The UI for the home page.
    """
    return rx.markdown(open("README.md").read(), component_map=styles.markdown_style)
