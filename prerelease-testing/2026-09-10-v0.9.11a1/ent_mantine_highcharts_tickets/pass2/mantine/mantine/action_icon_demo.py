"""Action icon demo page."""

import reflex as rx

import reflex_enterprise as rxe

from .common import demo


class ActionIconState(rx.State):
    """State for the action icon demo."""

    count: int = 0

    @rx.event
    def increment(self):
        self.count += 1

    @rx.event
    def decrement(self):
        self.count -= 1


@demo(
    route="/action-icon",
    title="Action Icon",
    description="An action icon is a small, button-like component that has an icon inside.",
)
def action_icon_page():
    """Action icon demo page."""
    return rx.hstack(
        rxe.action_icon(
            rx.icon("minus"),
            on_click=ActionIconState.decrement,
            size="xl",
            variant="gradient",
            disabled=ActionIconState.count <= 0,
            gradient={"from": "red", "to": "orange", "deg": 90},
        ),
        rx.text(f"Count: {ActionIconState.count}"),
        rxe.action_icon(
            rx.icon("plus"),
            on_click=ActionIconState.increment,
            size="xl",
            variant="gradient",
            disabled=ActionIconState.count >= 10,
            gradient={"from": "blue", "to": "cyan", "deg": 90},
        ),
        align="center",
        spacing="4",
    )
