"""One button, one counter, on reflex-enterprise."""

import reflex as rx

import reflex_enterprise as rxe


class CounterState(rx.State):
    """A trivial counter."""

    count: int = 0

    @rx.event
    def inc(self):
        """Increment the counter."""
        self.count += 1


def index() -> rx.Component:
    """The only page.

    Returns:
        The page component.
    """
    return rx.vstack(
        rx.heading(CounterState.count.to_string(), id="count"),
        rx.button("Increment", on_click=CounterState.inc, id="inc"),
    )


app = rxe.App()
app.add_page(index, route="/")
