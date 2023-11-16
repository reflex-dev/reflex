"""Welcome to Reflex! This file outlines the steps to create a basic app."""
from typing import Callable

import reflex as rx

from .pages import chatapp_page, datatable_page, forms_page, graphing_page, home_page
from .sidebar import sidebar
from .state import State
from .styles import *

meta = [
    {
        "name": "viewport",
        "content": "width=device-width, shrink-to-fit=no, initial-scale=1",
    },
]


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
                rx.menu_item(
                    rx.link("About", href="https://github.com/reflex-dev", width="100%")
                ),
                rx.menu_item(
                    rx.link("Contact", href="mailto:founders@=reflex.dev", width="100%")
                ),
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
        transition="left 0.5s, width 0.5s",
        position="relative",
        left=rx.cond(State.sidebar_displayed, "0px", f"-{sidebar_width}"),
    )


@rx.page("/", meta=meta)
@template
def home() -> rx.Component:
    """Home page.

    Returns:
        rx.Component: The home page.
    """
    return home_page()


@rx.page("/forms", meta=meta)
@template
def forms() -> rx.Component:
    """Forms page.

    Returns:
        rx.Component: The settings page.
    """
    return forms_page()


@rx.page("/graphing", meta=meta)
@template
def graphing() -> rx.Component:
    """Graphing page.

    Returns:
        rx.Component: The graphing page.
    """
    return graphing_page()


@rx.page("/datatable", meta=meta)
@template
def datatable() -> rx.Component:
    """Data Table page.

    Returns:
        rx.Component: The chatapp page.
    """
    return datatable_page()


@rx.page("/chatapp", meta=meta)
@template
def chatapp() -> rx.Component:
    """Chatapp page.

    Returns:
        rx.Component: The chatapp page.
    """
    return chatapp_page()


# Add state and page to the app.
app = rx.App(style=base_style)
app.compile()
