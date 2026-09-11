"""Minimal app instrumented exactly as the published reflex-otel README says."""

import reflex as rx
from reflex_otel import ReflexInstrumentor

ReflexInstrumentor().instrument()


class State(rx.State):
    """Counter state."""

    count: int = 0

    @rx.event
    def inc(self):
        """Increment the counter."""
        self.count += 1


def index() -> rx.Component:
    """Index page."""
    return rx.vstack(
        rx.text(State.count, id="count"),
        rx.button("inc", on_click=State.inc, id="inc"),
        rx.text("ready", id="ready"),
    )


app = rx.App()
app.add_page(index)
