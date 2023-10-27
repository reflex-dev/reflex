"""Sidebar component for the app."""

from code import styles
from code.state import State

import reflex as rx


def sidebar_header() -> rx.Component:
    """Sidebar header.

    Returns:
        The sidebar header component.
    """
    return rx.hstack(
        # The logo.
        rx.image(
            src="/icon.svg",
            height="2em",
        ),
        rx.spacer(),
        # Link to Reflex GitHub repo.
        rx.link(
            rx.center(
                rx.image(
                    src="/github.svg",
                    height="3em",
                    padding="0.5em",
                ),
                box_shadow=styles.box_shadow,
                bg="transparent",
                border_radius=styles.border_radius,
                _hover={
                    "bg": styles.accent_color,
                },
            ),
            href="https://github.com/reflex-dev/reflex",
        ),
        width="100%",
        border_bottom=styles.border,
        padding="1em",
    )


def sidebar_footer() -> rx.Component:
    """Sidebar footer.

    Returns:
        The sidebar footer component.
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
                border_radius=styles.border_radius,
                **styles.hover_accent_bg,
            ),
            on_click=State.toggle_sidebar_displayed,
            transform=rx.cond(~State.sidebar_displayed, "rotate(180deg)", ""),
            transition="transform 0.5s, left 0.5s",
            position="relative",
            left=rx.cond(State.sidebar_displayed, "0px", "20.5em"),
            **styles.overlapping_button_style,
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
        border_top=styles.border,
        padding="1em",
    )


def sidebar_item(text: str, icon: str, url: str) -> rx.Component:
    """Sidebar item.

    Args:
        text: The text of the item.
        icon: The icon of the item.
        url: The URL of the item.

    Returns:
        rx.Component: The sidebar item component.
    """
    # Whether the item is active.
    active = (State.router.page.path == f"/{text.lower()}") | (
        (State.router.page.path == "/") & text == "Home"
    )

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
                active,
                styles.accent_color,
                "transparent",
            ),
            color=rx.cond(
                active,
                styles.accent_text_color,
                styles.text_color,
            ),
            border_radius=styles.border_radius,
            box_shadow=styles.box_shadow,
            width="100%",
            padding_x="1em",
        ),
        href=url,
        width="100%",
    )


def sidebar() -> rx.Component:
    """The sidebar.

    Returns:
        The sidebar component.
    """
    # Get all the decorated pages and add them to the sidebar.
    from reflex.page import get_decorated_pages

    return rx.box(
        rx.vstack(
            sidebar_header(),
            rx.vstack(
                *[
                    sidebar_item(
                        text=page.get("title", page["route"].strip("/").capitalize()),
                        icon=page.get("image", "/github.svg"),
                        url=page["route"],
                    )
                    for page in get_decorated_pages()
                ],
                width="100%",
                overflow_y="auto",
                align_items="flex-start",
                padding="1em",
            ),
            rx.spacer(),
            sidebar_footer(),
            height="100dvh",
        ),
        min_width=styles.sidebar_width,
        height="100%",
        position="sticky",
        top="0px",
        border_right=styles.border,
    )
