"""fix022 probe app: a counter driven over the event websocket."""

import reflex as rx


class S(rx.State):
    count: int = 0

    @rx.event
    def inc(self):
        self.count += 1


def index():
    return rx.vstack(
        rx.heading("fapp"),
        rx.text("count=", S.count, id="count"),
        rx.button("inc", on_click=S.inc, id="inc"),
    )


app = rx.App()
app.add_page(index)
