"""Welcome to Reflex! This file outlines the steps to create a basic app."""
from typing import Callable

import reflex as rx

from .pages import dashboard_page, home_page, settings_page
from .sidebar import sidebar
from .styles import *


def template(main_content: Callable[[], rx.Component]) -> rx.Component:
    """The template for each page of the app.

    Args:
        main_content (Callable[[], rx.Component]): The main content of the page.

    Returns:
        rx.Component: The template for each page of the app.
    """
    menu_button = rx.box(
        rx.menu(
            rx.menu_button(
                rx.icon(
                    tag="hamburger",
                    size="4em",
                    color=text_color,
                ),
            ),
            rx.menu_list(
                rx.menu_item(rx.link("Home", href="/", width="100%")),
                rx.menu_divider(),
                rx.menu_item(rx.link("About", href="https://github.com/reflex-dev", width="100%")),
                rx.menu_item(rx.link("Contact", href="mailto:founders@=reflex.dev", width="100%")),
            ),
        ),
        position="fixed",
        right="1.5em",
        top="1.5em",
        z_index="500",
    )

    return rx.hstack(
        sidebar(),
        main_content(),
        rx.spacer(),
        menu_button,
        align_items="flex-start",
    )


@rx.page("/")
@template
def home() -> rx.Component:
    """Home page.

    Returns:
        rx.Component: The home page.
    """
    return home_page()


@rx.page("/settings")
@template
def settings() -> rx.Component:
    """Settings page.

    Returns:
        rx.Component: The settings page.
    """
    return settings_page()


@rx.page("/dashboard")
@template
def dashboard() -> rx.Component:
    """Dashboard page.

    Returns:
        rx.Component: The dashboard page.
    """
    return dashboard_page()


# Add state and page to the app.
app = rx.App(style=base_style)
app.compile()
