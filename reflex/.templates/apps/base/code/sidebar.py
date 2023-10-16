"""Sidebar component for the app."""

import reflex as rx

from .state import State
from .styles import *


def sidebar_header() -> rx.Component:
    """Sidebar header.

    Returns:
        rx.Component: The sidebar header component.
    """
    return rx.hstack(
        rx.image(
            src="/icon.svg",
            height="2em",
        ),
        rx.spacer(),
        rx.link(
            rx.center(
                rx.image(
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
            href="https://github.com/reflex-dev/reflex",
        ),
        width="100%",
        border_bottom=border,
        padding="1em",
    )


def sidebar_footer() -> rx.Component:
    """Sidebar footer.

    Returns:
        rx.Component: The sidebar footer component.
    """
    return rx.hstack(
        rx.link(
            rx.center(
                rx.image(
                    src="/paneleft.svg",
                    height="2em",
                    padding="0.5em",
                ),
                bg="transparent",
                border_radius=border_radius,
                _hover={
                    "bg": accent_color,
                },
            ),
            href="https://github.com/reflex-dev/reflex",
        ),
        rx.spacer(),
        rx.link(
            rx.text(
                "Docs",
            ),
            href="https://reflex.dev/docs/getting-started/introduction/",
        ),
        rx.link(
            rx.text(
                "Blog",
            ),
            href="https://reflex.dev/blog/",
        ),
        width="100%",
        border_top=border,
        padding="1em",
    )


def sidebar_item(text: str, icon: str, url: str) -> rx.Component:
    """Sidebar item.

    Args:
        text (str): The text of the item.
        icon (str): The icon of the item.
        url (str): The URL of the item.

    Returns:
        rx.Component: The sidebar item component.
    """
    return rx.link(
        rx.hstack(
            rx.image(
                src=icon,
                height="2.5em",
                padding="0.5em",
            ),
            rx.text(
                text,
            ),
            bg=rx.cond(
                State.origin_url == f"/{text.lower()}/",
                accent_color,
                "transparent",
            ),
            color=rx.cond(
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


def sidebar() -> rx.Component:
    """Sidebar.

    Returns:
        rx.Component: The sidebar component.
    """
    return rx.box(
        rx.vstack(
            sidebar_header(),
            rx.vstack(
                sidebar_item(
                    "Dashboard",
                    "/github.svg",
                    "/dashboard",
                ),
                sidebar_item(
                    "Settings",
                    "/github.svg",
                    "/settings",
                ),
                width="100%",
                align_items="flex-start",
                padding="1em",
            ),
            rx.spacer(),
            sidebar_footer(),
            height="100vh",
        ),
        min_width="20em",
        width="25em",
        height="100%",
        left="0px",
        top="0px",
        border_right=border,
    )
