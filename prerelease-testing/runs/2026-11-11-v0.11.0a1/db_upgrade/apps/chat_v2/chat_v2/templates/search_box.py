from __future__ import annotations

from dataclasses import dataclass, field

import reflex as rx

from chat_v2.components.badges import sidebar_shortcut


@dataclass
class Style:
    default: dict[str, str | rx.Component] = field(
        default_factory=lambda: {
            "spacing": "1",
            "display": "flex",
            "align": "center",
            "border_radius": "8px",
            "padding": "5px 5px 5px 10px",
            "border": rx.color_mode_cond(
                f"1px solid {rx.color('indigo', 3)}",
                f"1px solid {rx.color('slate', 7, True)}",
            ),
            "background": rx.color_mode_cond(
                rx.color(
                    "indigo",
                    1,
                ),
                "",
            ),
            "box_shadow": rx.color_mode_cond(
                "0px 1px 3px rgba(25, 33, 61, 0.1)",
                "none",
            ),
        },
    )


SEARCH_BAR_STYLE: Style = Style()


def _search_bar_base(
    *args,
    **kwargs,
):
    """Creates a common search box."""
    return rx.hstack(
        rx.icon(
            tag="search",
            size=14,
            color=rx.color(
                "slate",
                11,
            ),
        ),
        rx.input(
            variant="soft",
            outline="none",
            placeholder="Search for chats...",
            background_color="transparent",
            color=rx.color("slate", 11),
        ),
        rx.spacer(),
        *args,
        **kwargs,
        **SEARCH_BAR_STYLE.default,
    )


def search_bar(
    **kwargs,
):
    """Creates a search box with a key binding shortcut UI."""
    return _search_bar_base(
        char=sidebar_shortcut(
            "K",
        ),
        **kwargs,
    )


def search_bar_with_sidebar_shortcut(
    **kwargs,
):
    """Creates a search box without a key binding shortcut."""
    return _search_bar_base(**kwargs)
