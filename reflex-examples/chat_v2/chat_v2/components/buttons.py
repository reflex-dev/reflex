from __future__ import annotations

from dataclasses import dataclass, field

import reflex as rx

from .loading_icon import loading_icon


@dataclass
class Style:
    default: dict[str, str | rx.Component] = field(
        default_factory=lambda: {
            "radius": "large",
            "cursor": "pointer",
            "variant": "classic",
            "padding": "18px 16px",
        },
    )


BUTTON_STYLE: Style = Style()


def button_with_icon(
    text: str,
    icon: str,
    is_loading: bool = False,
    **kwargs,
):
    """Creates a button with an icon.
    - text: The text of the button.
    - icon: The icon tag name.
    - **kwargs: Additional keyword arguments for rx.button.
    """
    return rx.button(
        rx.cond(
            is_loading,
            loading_icon(
                height="1em",
            ),
            rx.hstack(
                rx.icon(
                    tag=icon,
                    size=14,
                ),
                rx.text(
                    text,
                    size="2",
                    align="center",
                    weight="medium",
                    font_family="Inter",
                ),
                gap="8px",
                width="100%",
                display="flex",
                align="center",
                justify="center",
            ),
        ),
        **BUTTON_STYLE.default,
        **kwargs,
    )
