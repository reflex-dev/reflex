"""The board page, a counter shared by the sessions linked to one board."""

import reflex as rx

from playground.layout import layout
from playground.state import BoardState


def board() -> rx.Component:
    """Render the board page.

    Returns:
        The join button, the shared counter and the last benchmark event.
    """
    return layout(
        rx.vstack(
            rx.heading("Board"),
            rx.button(
                "Join the lobby", on_click=BoardState.join("lobby"), id="board-join"
            ),
            rx.hstack(
                rx.text(BoardState.count, id="board-count", size="6"),
                rx.button("+", on_click=BoardState.increment, id="board-increment"),
                align="center",
            ),
            rx.text(
                "Last benchmark event: ",
                BoardState.last_seq,
                " from client ",
                BoardState.last_client,
                id="board-seq",
            ),
        )
    )
