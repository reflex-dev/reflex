"""Minimal app exposing event handlers + a custom state resource over MCP."""

import reflex as rx

import reflex_enterprise as rxe


class CounterState(rx.State):
    """Simple counter state driven over MCP."""

    count: int = 0
    label: str = "hello"

    @rx.event
    def increment(self, amount: int):
        """Increment the counter by amount."""
        self.count += amount

    @rx.event
    def set_label_value(self, value: str):
        """Set the label."""
        self.label = value

    @rx.var
    def doubled(self) -> int:
        """Computed var: twice the count."""
        return self.count * 2

    @rxe.mcp.resource
    def summary(self) -> dict:
        """Summary of the counter session state."""
        return {"count": self.count, "label": self.label}


def index() -> rx.Component:
    """Index page."""
    return rx.vstack(
        rx.heading("MCP test app"),
        rx.text(CounterState.count, id="count"),
        rx.text(CounterState.label, id="label"),
        rx.button("inc", on_click=CounterState.increment(1), id="inc"),
    )


app = rxe.App()
app.add_page(index)
