"""Welcome to Nextpy! This file outlines the steps to create a basic app."""
from typing import Callable

import nextpy as xt

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


def template(main_content: Callable[[], xt.Component]) -> xt.Component:
    """The template for each page of the app.

    Args:
        main_content (Callable[[], xt.Component]): The main content of the page.

    Returns:
        xt.Component: The template for each page of the app.
    """
    menu_button = xt.box(
        xt.menu(
            xt.menu_button(
                xt.icon(
                    tag="hamburger",
                    size="4em",
                    color=text_color,
                ),
            ),
            xt.menu_list(
                xt.menu_item(xt.link("Home", href="/", width="100%")),
                xt.menu_divider(),
                xt.menu_item(
                    xt.link("About", href="https://github.com/dot-agent", width="100%")
                ),
                xt.menu_item(
                    xt.link("Contact", href="mailto:anurag@dotagent.ai", width="100%")
                ),
            ),
        ),
        position="fixed",
        right="1.5em",
        top="1.5em",
        z_index="500",
    )

    return xt.hstack(
        sidebar(),
        main_content(),
        xt.spacer(),
        menu_button,
        align_items="flex-start",
        transition="left 0.5s, width 0.5s",
        position="relative",
        left=xt.cond(State.sidebar_displayed, "0px", f"-{sidebar_width}"),
    )


@xt.page("/", meta=meta)
@template
def home() -> xt.Component:
    """Home page.

    Returns:
        xt.Component: The home page.
    """
    return home_page()


@xt.page("/forms", meta=meta)
@template
def forms() -> xt.Component:
    """Forms page.

    Returns:
        xt.Component: The settings page.
    """
    return forms_page()


@xt.page("/graphing", meta=meta)
@template
def graphing() -> xt.Component:
    """Graphing page.

    Returns:
        xt.Component: The graphing page.
    """
    return graphing_page()


@xt.page("/datatable", meta=meta)
@template
def datatable() -> xt.Component:
    """Data Table page.

    Returns:
        xt.Component: The chatapp page.
    """
    return datatable_page()


@xt.page("/chatapp", meta=meta)
@template
def chatapp() -> xt.Component:
    """Chatapp page.

    Returns:
        xt.Component: The chatapp page.
    """
    return chatapp_page()


# Add state and page to the app.
app = xt.App(style=base_style)
app.compile()
