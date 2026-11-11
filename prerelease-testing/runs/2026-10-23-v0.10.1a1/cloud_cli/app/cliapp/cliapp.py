"""QA app for the deploy archive test."""

import reflex as rx


class State(rx.State):
    count: int = 0

    def incr(self):
        self.count += 1


def index() -> rx.Component:
    return rx.container(
        rx.heading("cliapp"),
        rx.image(src="/logo.png", width="40px"),
        rx.text(State.count),
        rx.button("+", on_click=State.incr),
    )


def about() -> rx.Component:
    return rx.text("about")


app = rx.App()
app.add_page(index)
app.add_page(about, route="/about")
