"""Exercise a source text edit without custom memo functions or dependencies."""

import os
from pathlib import Path

import reflex as rx

from .label import LABEL

assert Path(rx.__file__).is_relative_to(
    Path(os.environ["SB"]) / "envs" / os.environ["QA_ENV"]
), rx.__file__


class State(rx.State):
    """Keep a counter so reloads also exercise backend event connections."""

    count: int = 0

    @rx.event
    def increment(self):
        """Increment this browser's counter."""
        self.count += 1


def index():
    """Render the changing label and a minimal stateful button.

    Returns:
        The test page.
    """
    return rx.vstack(
        rx.heading(LABEL, id="phase"),
        rx.text(State.count, id="count"),
        rx.button("Increment", on_click=State.increment, id="increment"),
        padding="24px",
    )


app = rx.App()
app.add_page(index)
