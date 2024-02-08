"""Sidebar component for the app."""

import reflex as rx

from .state import State
from .styles import *


def sidebar_header() -> rx.Component:
    """Sidebar header.

    Returns:
        rx.Component: The sidebar header component.
    """
    return rx.chakra.hstack(
        rx.chakra.image(
            src="/icon.svg",
            height="2em",
        ),
        rx.chakra.spacer(),
        rx.chakra.link(
            rx.chakra.center(
                rx.chakra.image(
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
    return rx.chakra.hstack(
        rx.chakra.link(
            rx.chakra.center(
                rx.chakra.image(
                    src="/paneleft.svg",
                    height="2em",
                    padding="0.5em",
                ),
                bg="transparent",
                border_radius=border_radius,
                **hover_accent_bg,
            ),
            on_click=State.toggle_sidebar_displayed,
            transform=rx.cond(~State.sidebar_displayed, "rotate(180deg)", ""),
            transition="transform 0.5s, left 0.5s",
            position="relative",
            left=rx.cond(State.sidebar_displayed, "0px", "20.5em"),
            **overlapping_button_style,
        ),
        rx.chakra.spacer(),
        rx.chakra.link(
            rx.chakra.text(
                "Docs",
            ),
            href="https://reflex.dev/docs/getting-started/introduction/",
        ),
        rx.chakra.link(
            rx.chakra.text(
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
    return rx.chakra.link(
        rx.chakra.hstack(
            rx.chakra.image(
                src=icon,
                height="2.5em",
                padding="0.5em",
            ),
            rx.chakra.text(
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
    return rx.chakra.box(
        rx.chakra.vstack(
            sidebar_header(),
            rx.chakra.vstack(
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
            rx.chakra.spacer(),
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
