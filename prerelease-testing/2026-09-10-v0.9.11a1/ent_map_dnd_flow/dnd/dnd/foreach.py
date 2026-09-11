"""Drag and Drop Foreach Demo."""

import reflex as rx

import reflex_enterprise as rxe

from .common import demo


class DndForeachState(rx.State):
    """The app state."""

    drop_points: list[int] = [0, 1, 2, 3]

    card_pos: int = 0

    @rx.event
    def set_card_pos(self, pos: int):
        """Set the card position."""
        self.card_pos = pos


@rx.memo
def card_foreach():
    return rxe.dnd.draggable(
        rx.card(
            rx.text("Draggable Thingy"),
            width="199px",
            height="199px",
        ),
        type="ForeachDraggable",
    )


@rx.memo
def target_foreach(pos: int = 0):
    params = rxe.dnd.DropTarget.collected_params
    return rxe.dnd.drop_target(
        rx.cond(DndForeachState.card_pos == pos, card_foreach()),
        width="200px",
        height="200px",
        border="1px solid red",
        on_drop=[
            rx.toast(f"Dropped in position {pos}"),
            DndForeachState.set_card_pos(pos),
        ],
        accept=["ForeachDraggable"],
        background_color=rx.cond(params.is_over, "green", "blue"),
    )


@demo(
    "/foreach",
    "Drag and Drop Foreach Demo",
    "Drag and Drop when using Foreach",
)
def foreach_page() -> rx.Component:
    return rx.container(
        rx.heading("Drag and Drop w/ Foreach"),
        rx.grid(
            rx.foreach(
                DndForeachState.drop_points,
                lambda pos: target_foreach(pos=pos),
            ),
            columns="4",
        ),
    )
