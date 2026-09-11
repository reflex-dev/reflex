"""Minimal app following docs/api-reference/observability.md verbatim."""

import reflex as rx

# the two lines the docs tell you to add
from reflex_otel import ReflexInstrumentor

ReflexInstrumentor().instrument()

assert "/envs/otel/" in rx.__file__, rx.__file__


class State(rx.State):
    """Counter state."""

    count: int = 0

    @rx.event
    def inc(self):
        """Increment."""
        self.count += 1


def index() -> rx.Component:
    """Index page.

    Returns:
        the page
    """
    return rx.vstack(
        rx.heading("verify2 otel"),
        rx.text(State.count, id="count"),
        rx.button("inc", on_click=State.inc, id="inc"),
    )


app = rx.App()
app.add_page(index)
