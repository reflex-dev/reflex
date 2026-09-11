"""App whose page registers a shared asset (rx.asset(shared=True))."""

import reflex as rx


def index() -> rx.Component:
    """Index page pulling in a shared asset."""
    return rx.fragment(
        rx.script(src=rx.asset(path="lib.js", shared=True)),
        rx.text("shared asset app"),
    )


app = rx.App()
app.add_page(index)
