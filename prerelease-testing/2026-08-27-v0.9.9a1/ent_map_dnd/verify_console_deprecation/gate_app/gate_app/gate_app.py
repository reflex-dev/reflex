"""Minimal rxe.App to trigger the enterprise login/prod gates."""

import reflex as rx
import reflex_enterprise as rxe


class State(rx.State):
    """Trivial state."""

    value: str = ""


def index() -> rx.Component:
    """Index page.

    Returns:
        The page component.
    """
    return rx.text("gate app", id="hello")


app = rxe.App()
app.add_page(index)
