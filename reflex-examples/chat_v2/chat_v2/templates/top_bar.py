from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import reflex as rx

from chat_v2.components.buttons import button_with_icon


@dataclass
class Style:
    """Style for the top bar."""

    icons: set[str] = (
        "settings",
        "trash",
        "archive",
        "panel-right",
    )
    default: dict[str, str | rx.Component] = field(
        default_factory=lambda: {
            "width": "100%",
            "display": "flex",
            "justify": "between",
            "padding": "16px 24px",
            "border_bottom": rx.color_mode_cond(
                light=f"2px solid {rx.color('indigo', 3)}",
                dark=f"1px solid {rx.color('slate', 7, True)}",
            ),
        },
    )
    component: dict[str, str] = field(
        default_factory=lambda: {
            "width": "400px",
            "display": "flex",
            "align": "center",
            "spacing": "6",
        },
    )


NAV_BAR_STYLE: Style = Style()


def nav_bar(
    on_create_new_chat: Callable,
):
    return rx.hstack(
        rx.hstack(
            # toggle theme
            rx.color_mode.button(),
            **NAV_BAR_STYLE.component,
        ),
        button_with_icon(
            text="New Chat",
            icon="plus",
            on_click=on_create_new_chat,
        ),
        **NAV_BAR_STYLE.default,
    )
