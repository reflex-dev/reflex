"""Drag and Drop Basic Demo."""

import reflex as rx

import reflex_enterprise as rxe

from .common import demo


class DndState(rx.State):
    """The app state."""

    drop_points: list[int] = [0, 1, 2, 3]

    card_pos: int = 0

    @rx.event
    def set_card_pos(self, pos: int):
        """Set the card position."""
        self.card_pos = pos


@rx.memo
def card():
    return rxe.dnd.draggable(
        rx.card(
            rx.text("Draggable Thingy"),
            width="199px",
            height="199px",
        ),
        type="BasicDraggable",
        border="1px solid black",
    )


def target(pos: int = 0):
    params = rxe.dnd.DropTarget.collected_params
    return rxe.dnd.drop_target(
        rx.cond(DndState.card_pos == pos, card()),
        width="200px",
        height="200px",
        border="1px solid red",
        accept=["BasicDraggable"],
        on_drop=[
            rx.toast(f"Dropped in position {pos}"),
            DndState.set_card_pos(pos),
        ],
        background_color=rx.cond(params.is_over, "green", "blue"),
    )


@demo(
    route="/basic",
    title="Drag and Drop Basic Demo",
    description="Drag and Drop when using basic components",
)
def basic_page() -> rx.Component:
    return rx.container(
        rx.heading("Drag and Drop Basic Demo"),
        rx.grid(
            target(0),
            target(1),
            target(2),
            target(3),
            columns="4",
        ),
    )
