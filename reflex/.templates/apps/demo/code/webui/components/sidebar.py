import reflex as rx

from ...webui import styles
from ...webui.state import State


def sidebar_chat(chat: str) -> rx.Component:
    """A sidebar chat item.

    Args:
        chat: The chat item.

    Returns:
        The sidebar chat item.
    """
    return rx.chakra.hstack(
        rx.chakra.box(
            chat,
            on_click=lambda: State.set_chat(chat),
            style=styles.sidebar_style,
            color=styles.icon_color,
            flex="1",
        ),
        rx.chakra.box(
            rx.chakra.icon(
                tag="delete",
                style=styles.icon_style,
                on_click=State.delete_chat,
            ),
            style=styles.sidebar_style,
        ),
        color=styles.text_light_color,
        cursor="pointer",
    )


def sidebar() -> rx.Component:
    """The sidebar component.

    Returns:
        The sidebar component.
    """
    return rx.chakra.drawer(
        rx.chakra.drawer_overlay(
            rx.chakra.drawer_content(
                rx.chakra.drawer_header(
                    rx.chakra.hstack(
                        rx.chakra.text("Chats"),
                        rx.chakra.icon(
                            tag="close",
                            on_click=State.toggle_drawer,
                            style=styles.icon_style,
                        ),
                    )
                ),
                rx.chakra.drawer_body(
                    rx.chakra.vstack(
                        rx.foreach(State.chat_titles, lambda chat: sidebar_chat(chat)),
                        align_items="stretch",
                    )
                ),
            ),
        ),
        placement="left",
        is_open=State.drawer_open,
    )
