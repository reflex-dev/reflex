"""Exercise actual enterprise production and export badge behavior."""

import reflex_enterprise as rxe

import reflex as rx


class State(rx.State):
    """Keep a counter for production event verification."""

    count: int = 0

    @rx.event
    def increment(self) -> None:
        """Increment the visible counter."""
        self.count += 1


def index() -> rx.Component:
    """Render the fixture app's production controls.

    Returns:
        The badge-policy app page.
    """
    return rx.vstack(
        rx.heading("Badge policy QA"),
        rx.text(State.count, id="count"),
        rx.button("Increment", on_click=State.increment),
    )


app = rxe.App()
app.add_page(index)
