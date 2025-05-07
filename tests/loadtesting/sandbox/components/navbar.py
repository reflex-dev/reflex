import reflex as rx
from sandbox.states.base import BaseState
from sandbox.styles import text

navbar: rx.Style = rx.Style(
    {
        "width": "100%",
        "padding": "1em 1.15em",
        "justify_content": "space-between",
        "background_color": rx.color_mode_cond(
            "rgba(255, 255, 255, 0.81)",
            "rgba(18, 17, 19, 0.81)",
        ),
        "align_items": "center",
        "border_bottom": "1px solid rgba(46, 46, 46, 0.51)",
    }
)


def render_navbar():
    return rx.hstack(
        rx.hstack(
            rx.box(
                rx.text(
                    "REST API Admin Panel",
                    font_size="var(--chakra-fontSizes-lg)",
                    style=rx.Style(text),
                ),
            ),
            display="flex",
            align_items="center",
        ),
        rx.hstack(
            rx.button(
                BaseState.is_request, on_click=BaseState.toggle_query, cursor="pointer"
            ),
            rx.color_mode.button(),
            align_items="center",
        ),
        style=navbar,
    )
