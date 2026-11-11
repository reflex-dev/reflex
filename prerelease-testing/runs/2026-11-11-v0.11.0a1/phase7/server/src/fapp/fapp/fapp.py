"""phase7 net probe app: a counter driven over the event websocket. EXPECT_VENV must prefix rx.__file__."""

import os

import reflex as rx

_V = os.environ.get("EXPECT_VENV", "")
assert _V and rx.__file__.startswith(_V + "/"), (_V, rx.__file__)


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
