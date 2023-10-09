import reflex as rx

from .state import State
from .styles import *


def sidebar_item(text: str, icon: str, url: str) -> rx.Component:
    return rx.hstack(
        rx.image(
            src=icon,
            height="2.5em",
            padding="0.5em",
        ),
        rx.text(
            text,
        ),
        bg=rx.cond(State.current_page == text, accent_color, "transparent"),
        color=rx.cond(State.current_page == text, accent_text_color, text_color),
        border_radius=border_radius,
        border="1px solid transparent",
        width="100%",
        padding_x="1em",
        _hover={
            "box_shadow": box_shadow,
        },
        on_click=lambda: State.set_page(text),
    )


def sidebar_header():
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
                    "bg": "#F5EFFE",
                },
            ),
            href="https://github.com/reflex-dev/reflex",
        ),
        width="100%",
        border_bottom=border,
        padding="1em",
    )


def sidebar_footer():
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
                on_click=State.toggle_sidebar,
                _hover={
                    "bg": "#F5EFFE",
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


def sidebar():
    return rx.box(
        rx.vstack(
            sidebar_header(),
            rx.vstack(
                sidebar_item(
                    "Dashboard",
                    "/github.svg",
                    "docs_url",
                ),
                sidebar_item(
                    "Settings",
                    "/github.svg",
                    "docs_url",
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
