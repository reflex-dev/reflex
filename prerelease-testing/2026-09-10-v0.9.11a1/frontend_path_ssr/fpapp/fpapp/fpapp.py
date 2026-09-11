"""App served under a frontend_path sub-path, for the #7044 export/prod claim."""

import reflex as rx


class State(rx.State):
    """Counter state."""

    count: int = 0

    @rx.var
    def doubled(self) -> int:
        """Twice the count."""
        return self.count * 2

    @rx.event
    def inc(self):
        """Increment."""
        self.count += 1


def index() -> rx.Component:
    """Index page."""
    return rx.container(
        rx.heading("frontend_path app"),
        rx.text(State.count, id="count"),
        rx.text(State.doubled, id="doubled"),
        rx.button("inc", on_click=State.inc, id="inc"),
        rx.link("about", href="/about", id="to-about"),
    )


def about() -> rx.Component:
    """Second page, to check sub-path routing."""
    return rx.container(
        rx.heading("about page", id="about-heading"),
        rx.link("home", href="/", id="to-home"),
    )


app = rx.App()
app.add_page(index)
app.add_page(about, route="/about")
