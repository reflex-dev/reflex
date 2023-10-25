"""Common templates used between pages in the app."""

from code import styles
from code.components.sidebar import sidebar
from code.state import State
from typing import Callable

import reflex as rx

# Meta tags for the app.
meta = [
    {
        "name": "viewport",
        "content": "width=device-width, shrink-to-fit=no, initial-scale=1",
    },
]


def menu_button() -> rx.Component:
    """The menu button on the top right of the page.

    Returns:
        The menu button component.
    """
    return rx.box(
        rx.menu(
            rx.menu_button(
                rx.icon(
                    tag="hamburger",
                    size="4em",
                    color=styles.text_color,
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


def template(
    **page_kwargs: dict,
) -> Callable[[Callable[[], rx.Component]], rx.Component]:
    """The template for each page of the app.

    Args:
        page_kwargs: Keyword arguments to pass to the page.

    Returns:
        The template with the page content.
    """

    def decorator(page_content: Callable[[], rx.Component]) -> rx.Component:
        """The template for each page of the app.

        Args:
            page_content: The content of the page.

        Returns:
            The template with the page content.
        """

        @rx.page(**page_kwargs, meta=meta)
        def templated_page():
            return rx.hstack(
                sidebar(),
                rx.box(
                    rx.box(
                        page_content(),
                        **styles.template_content_style,
                    ),
                    **styles.template_page_style,
                ),
                rx.spacer(),
                menu_button(),
                align_items="flex-start",
                transition="left 0.5s, width 0.5s",
                position="relative",
                left=rx.cond(
                    State.sidebar_displayed, "0px", f"-{styles.sidebar_width}"
                ),
            )

        return templated_page

    return decorator
