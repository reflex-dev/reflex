"""Minimal reflex-enterprise app used to probe the prod/export paid-tier gate."""

import reflex as rx
import reflex_enterprise as rxe

assert "/envs/" in rx.__file__, rx.__file__


class State(rx.State):
    n: int = 0

    @rx.event
    def inc(self):
        self.n += 1


def index():
    return rx.vstack(
        rx.heading("minimal rxe"),
        rx.text(State.n.to_string(), id="n"),
        rx.button("inc", on_click=State.inc, id="inc"),
    )


app = rxe.App()
app.add_page(index, route="/")
