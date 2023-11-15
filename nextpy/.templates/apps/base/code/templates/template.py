"""Common templates used between pages in the app."""

from __future__ import annotations

from code import styles
from code.components.sidebar import sidebar
from typing import Callable

import nextpy as xt

# Meta tags for the app.
default_meta = [
    {
        "name": "viewport",
        "content": "width=device-width, shrink-to-fit=no, initial-scale=1",
    },
]


def menu_button() -> xt.Component:
    """The menu button on the top right of the page.

    Returns:
        The menu button component.
    """
    from nextpy.core.page import get_decorated_pages

    return xt.box(
        xt.menu(
            xt.menu_button(
                xt.icon(
                    tag="hamburger",
                    size="4em",
                    color=styles.text_color,
                ),
            ),
            xt.menu_list(
                *[
                    xt.menu_item(
                        xt.link(
                            page["title"],
                            href=page["route"],
                            width="100%",
                        )
                    )
                    for page in get_decorated_pages()
                ],
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


def template(
    route: str | None = None,
    title: str | None = None,
    image: str | None = None,
    description: str | None = None,
    meta: str | None = None,
    script_tags: list[xt.Component] | None = None,
    on_load: xt.event.EventHandler | list[xt.event.EventHandler] | None = None,
) -> Callable[[Callable[[], xt.Component]], xt.Component]:
    """The template for each page of the app.

    Args:
        route: The route to reach the page.
        title: The title of the page.
        image: The favicon of the page.
        description: The description of the page.
        meta: Additionnal meta to add to the page.
        on_load: The event handler(s) called when the page load.
        script_tags: Scripts to attach to the page.

    Returns:
        The template with the page content.
    """

    def decorator(page_content: Callable[[], xt.Component]) -> xt.Component:
        """The template for each page of the app.

        Args:
            page_content: The content of the page.

        Returns:
            The template with the page content.
        """
        # Get the meta tags for the page.
        all_meta = [*default_meta, *(meta or [])]

        @xt.page(
            route=route,
            title=title,
            image=image,
            description=description,
            meta=all_meta,
            script_tags=script_tags,
            on_load=on_load,
        )
        def templated_page():
            return xt.hstack(
                sidebar(),
                xt.box(
                    xt.box(
                        page_content(),
                        **styles.template_content_style,
                    ),
                    **styles.template_page_style,
                ),
                menu_button(),
                align_items="flex-start",
                transition="left 0.5s, width 0.5s",
                position="relative",
            )

        return templated_page

    return decorator
