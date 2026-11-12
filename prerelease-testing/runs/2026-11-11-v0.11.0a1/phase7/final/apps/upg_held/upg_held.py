"""Blank template plus a counter, a bound input and a few sibling-package components."""

import reflex as rx


class State(rx.State):
    """The app state."""

    count: int = 0
    name: str = ""

    @rx.event
    def increment(self):
        """Add one to the counter."""
        self.count += 1

    @rx.event
    def set_name_upper(self, value: str):
        """Store the typed name upper-cased."""
        self.name = value.upper()


def index() -> rx.Component:
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Welcome to Reflex!", size="9"),
            rx.hstack(rx.icon("heart"), rx.text("Count: ", State.count, id="count")),
            rx.button("Increment", on_click=State.increment, id="inc"),
            rx.input(placeholder="name", on_change=State.set_name_upper, id="name"),
            rx.text("Hello ", State.name, id="hello"),
            rx.callout("Callout text", icon="info"),
            rx.code_block("print('hi')", language="python"),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)
