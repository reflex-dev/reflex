"""Minimal app for the #6960 telemetry-context check."""

import reflex as rx


class State(rx.State):
    """Counter state."""

    count: int = 0

    @rx.event
    def inc(self):
        """Increment."""
        self.count += 1


def index() -> rx.Component:
    """Index page."""
    return rx.container(rx.text(State.count, id="count"), rx.button("inc", on_click=State.inc, id="inc"))


app = rx.App()
app.add_page(index)
