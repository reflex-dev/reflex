"""The room page: sessions on one URL share a board, see who is there and each other's updates."""

import reflex as rx

from playground.layout import layout
from playground.state import BoardState
from playground.states.room import RoomState


def room() -> rx.Component:
    """Render a room, a dynamic route that joins its board on load.

    Returns:
        Who is in the room, the shared counter and the broadcast controls.
    """
    return layout(
        rx.vstack(
            rx.heading("Room ", rx.code(RoomState.room, id="room-name")),
            rx.text(
                "Open this page in another tab or browser: every session on the same "
                "room URL shares the counter below and sees who else is here."
            ),
            rx.hstack(
                rx.text("You are ", rx.text.strong(RoomState.name, id="room-me")),
                rx.button(
                    "Leave",
                    on_click=RoomState.leave,
                    variant="soft",
                    color_scheme="gray",
                    id="room-leave",
                ),
                align="center",
            ),
            rx.hstack(
                rx.text(
                    "Here: ", BoardState.members.length(), id="room-presence-count"
                ),
                rx.hstack(
                    rx.foreach(
                        BoardState.members,
                        lambda member: rx.badge(member, variant="surface"),
                    ),
                    wrap="wrap",
                    id="room-presence",
                ),
                align="center",
            ),
            rx.hstack(
                rx.text(BoardState.count, id="room-count", size="6"),
                rx.button("+", on_click=BoardState.increment, id="room-increment"),
                rx.button(
                    "+10 at once",
                    on_click=RoomState.burst,
                    variant="soft",
                    id="room-burst",
                ),
                align="center",
            ),
            rx.hstack(
                rx.button(
                    "Broadcast", on_click=RoomState.broadcast, id="room-broadcast"
                ),
                rx.text(
                    "Last broadcast: ",
                    BoardState.last_seq,
                    " from client ",
                    BoardState.last_client,
                    id="room-last",
                ),
                align="center",
            ),
            spacing="3",
        )
    )
