import reflex as rx


class State(rx.State):
    count: int = 0

    @rx.event
    def inc(self):
        self.count += 1


def index():
    return rx.vstack(
        rx.heading("cfgapp"),
        rx.text(State.count, id="count"),
        rx.button("inc", on_click=State.inc, id="inc"),
    )


app = rx.App()
app.add_page(index)
