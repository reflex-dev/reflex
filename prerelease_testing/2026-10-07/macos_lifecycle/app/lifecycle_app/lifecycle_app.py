"""Small browser fixture for startup, events, and hot reload."""

import os

import reflex as rx

assert f"/envs/{os.environ['REFLEX_TEST_ENV']}/" in rx.__file__, rx.__file__


class State(rx.State):
    """State used to exercise the browser/backend connection."""

    count: int = 0
    name: str = ""

    @rx.event
    def increment(self):
        """Increment the count with a hot-reloadable step."""
        self.count += 1

    @rx.event
    def rename(self, value: str):
        """Store the input value.

        Args:
            value: The typed text.
        """
        self.name = value


def index():
    """Render the lifecycle test controls.

    Returns:
        A stack of event controls and their state.
    """
    return rx.vstack(
        rx.heading("Lifecycle version one", id="heading"),
        rx.text(State.count, id="count"),
        rx.button("Increment", on_click=State.increment),
        rx.input(placeholder="Name", on_change=State.rename),
        rx.text(State.name, id="name"),
        padding="2em",
    )


app = rx.App()
app.add_page(index)
