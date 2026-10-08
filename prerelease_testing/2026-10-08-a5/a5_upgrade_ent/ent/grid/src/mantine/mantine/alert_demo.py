"""Alert demo page."""

import reflex as rx

import reflex_enterprise as rxe

from .common import demo


class AlertState(rx.State):
    """State for the alert demo."""

    show_alert: bool = True

    @rx.event
    def toggle_alert(self):
        self.show_alert = not self.show_alert


@demo(
    route="/alert",
    title="Alert",
    description="An alert is used to display important information to the user.",
)
def alert_page():
    """Alert demo page."""
    return rx.hstack(
        rxe.alert(
            "Lorem ipsum dolor sit, amet consectetur adipisicing elit. At officiis, quae tempore necessitatibus placeat saepe.",
            icon=rx.icon("info"),
            title="Alert",
            variant="light",
            color="blue",
            with_close_button=True,
            radius="lg",
            on_close=AlertState.toggle_alert,
            display=rx.cond(AlertState.show_alert, "block", "none"),
        ),
        rx.cond(
            ~AlertState.show_alert,
            rxe.action_icon(
                rx.icon("eye"),
                on_click=AlertState.toggle_alert,
                size="lg",
            ),
        ),
        align="center",
        spacing="4",
    )
