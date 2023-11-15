"""Sidebar component for the app."""

import nextpy as xt

from .state import State
from .styles import *


def sidebar_header() -> xt.Component:
    """Sidebar header.

    Returns:
        xt.Component: The sidebar header component.
    """
    return xt.hstack(
        xt.image(
            src="/icon.svg",
            height="2em",
        ),
        xt.spacer(),
        xt.link(
            xt.center(
                xt.image(
                    src="/github.svg",
                    height="3em",
                    padding="0.5em",
                ),
                box_shadow=box_shadow,
                bg="transparent",
                border_radius=border_radius,
                _hover={
                    "bg": accent_color,
                },
            ),
            href="https://github.com/dot-agent",
        ),
        width="100%",
        border_bottom=border,
        padding="1em",
    )


def sidebar_footer() -> xt.Component:
    """Sidebar footer.

    Returns:
        xt.Component: The sidebar footer component.
    """
    return xt.hstack(
        xt.link(
            xt.center(
                xt.image(
                    src="/paneleft.svg",
                    height="2em",
                    padding="0.5em",
                ),
                bg="transparent",
                border_radius=border_radius,
                **hover_accent_bg,
            ),
            on_click=State.toggle_sidebar_displayed,
            transform=xt.cond(~State.sidebar_displayed, "rotate(180deg)", ""),
            transition="transform 0.5s, left 0.5s",
            position="relative",
            left=xt.cond(State.sidebar_displayed, "0px", "20.5em"),
            **overlapping_button_style,
        ),
        xt.spacer(),
        xt.link(
            xt.text(
                "Docs",
            ),
            href="https://docs.dotagent.dev/nextpy/getting-started/introduction/",
        ),
        xt.link(
            xt.text(
                "Blog",
            ),
            href="https://dotagent.dev/blog/",
        ),
        width="100%",
        border_top=border,
        padding="1em",
    )


def sidebar_item(text: str, icon: str, url: str) -> xt.Component:
    """Sidebar item.

    Args:
        text (str): The text of the item.
        icon (str): The icon of the item.
        url (str): The URL of the item.

    Returns:
        xt.Component: The sidebar item component.
    """
    return xt.link(
        xt.hstack(
            xt.image(
                src=icon,
                height="2.5em",
                padding="0.5em",
            ),
            xt.text(
                text,
            ),
            bg=xt.cond(
                State.origin_url == f"/{text.lower()}/",
                accent_color,
                "transparent",
            ),
            color=xt.cond(
                State.origin_url == f"/{text.lower()}/",
                accent_text_color,
                text_color,
            ),
            border_radius=border_radius,
            box_shadow=box_shadow,
            width="100%",
            padding_x="1em",
        ),
        href=url,
        width="100%",
    )


def sidebar() -> xt.Component:
    """Sidebar.

    Returns:
        xt.Component: The sidebar component.
    """
    return xt.box(
        xt.vstack(
            sidebar_header(),
            xt.vstack(
                sidebar_item(
                    "Welcome",
                    "/github.svg",
                    "/",
                ),
                sidebar_item(
                    "Graphing Demo",
                    "/github.svg",
                    "/graphing",
                ),
                sidebar_item(
                    "Data Table Demo",
                    "/github.svg",
                    "/datatable",
                ),
                sidebar_item(
                    "Forms Demo",
                    "/github.svg",
                    "/forms",
                ),
                sidebar_item(
                    "Chat App Demo",
                    "/github.svg",
                    "/chatapp",
                ),
                width="100%",
                overflow_y="auto",
                align_items="flex-start",
                padding="1em",
            ),
            xt.spacer(),
            sidebar_footer(),
            height="100dvh",
        ),
        display=["none", "none", "block"],
        min_width=sidebar_width,
        height="100%",
        position="sticky",
        top="0px",
        border_right=border,
    )
