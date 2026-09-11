"""Valid prefixed app for the FINDING-014 build/export control."""

import reflex as rx


class State(rx.State):
    """Counter."""

    count: int = 0

    @rx.event
    def inc(self):
        """Increment."""
        self.count += 1


def index() -> rx.Component:
    """Index page."""
    return rx.vstack(rx.text(State.count, id="count"),
                     rx.button("inc", on_click=State.inc, id="inc"),
                     rx.text("ready", id="ready"))


app = rx.App()
app.add_page(index)
