import reflex as rx


class State(rx.State):
    count: int = 0

    @rx.event
    def incr(self):
        self.count += 1


def index() -> rx.Component:
    return rx.vstack(
        rx.heading("verify prod build warnings", id="hd"),
        rx.text(State.count, id="count"),
        rx.button("+1", id="btn", on_click=State.incr),
    )


app = rx.App()
app.add_page(index)
