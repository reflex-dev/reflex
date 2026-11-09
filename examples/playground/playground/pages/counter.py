"""The counter page, a simple event round trip."""

import reflex as rx

from playground.layout import layout
from playground.state import PlaygroundState


def counter() -> rx.Component:
    """Render the counter page.

    Returns:
        The counter, its buttons and its parity.
    """
    return layout(
        rx.vstack(
            rx.heading("Counter"),
            rx.hstack(
                rx.button("-", on_click=PlaygroundState.decrement, id="decrement"),
                rx.text(PlaygroundState.count, id="count", size="6"),
                rx.button("+", on_click=PlaygroundState.increment, id="increment"),
                align="center",
            ),
            rx.cond(
                PlaygroundState.count % 2 == 0,
                rx.badge("even"),
                rx.badge("odd", color_scheme="orange"),
            ),
        )
    )
