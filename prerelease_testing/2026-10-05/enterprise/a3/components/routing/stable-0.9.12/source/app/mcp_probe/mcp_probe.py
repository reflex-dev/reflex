"""Minimal MCP app for published production routing comparison."""

import reflex as rx
import reflex_enterprise as rxe


class State(rx.State):
    """Expose a small anonymous event surface."""

    count: int = 0

    @rxe.event
    def bump(self) -> None:
        """Increment this session counter."""
        self.count += 1


def index() -> rx.Component:
    """Render a production readiness marker.

    Returns:
        Counter and readiness heading.
    """
    return rx.box(rx.heading("MCP routing probe"), rx.text(State.count))


app = rxe.App()
app.add_page(index)
