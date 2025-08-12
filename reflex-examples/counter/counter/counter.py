"""An simple example of a counter app using Reflex."""

import reflex as rx
import random


class State(rx.State):
    """The State defines reactive variables and the event handlers that can modify them."""

    count: int = 0

    def increment(self):
        """Increment the count."""
        self.count += 1

    def decrement(self):
        """Decrement the count."""
        self.count -= 1

    def random(self):
        """Randomize the count."""
        self.count = random.randint(0, 100)


def index():
    """The main view."""
    return rx.center(
        rx.color_mode.button(position="top-right"),
        rx.card(
            rx.vstack(
                rx.heading(State.count),
                rx.hstack(
                    rx.button(
                        "Decrement",
                        on_click=State.decrement,
                        color_scheme="red",
                    ),
                    rx.button(
                        "Randomize",
                        on_click=State.random,
                        background_image="linear-gradient(90deg, rgba(255,0,0,1) 0%, rgba(0,176,34,1) 100%)",
                        color="white",
                    ),
                    rx.button(
                        "Increment",
                        on_click=State.increment,
                        color_scheme="green",
                    ),
                ),
                align="center",
            ),
            size="4",
        ),
        padding_top="5em",
    )


app = rx.App()
app.add_page(index, title="Counter")
