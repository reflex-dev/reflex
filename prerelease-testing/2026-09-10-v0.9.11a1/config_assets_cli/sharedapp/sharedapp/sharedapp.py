import reflex as rx

from .widget import CSS_PATH, JS_PATH, widget


class State(rx.State):
    n: int = 0

    @rx.event
    def bump(self):
        self.n += 1


def index():
    return rx.vstack(
        rx.heading("sharedapp", id="title"),
        widget(),
        rx.text(CSS_PATH, id="css-path"),
        rx.text(JS_PATH, id="js-path"),
        rx.text(State.n, id="n"),
        rx.button("bump", on_click=State.bump, id="bump"),
    )


app = rx.App()
app.add_page(index)
