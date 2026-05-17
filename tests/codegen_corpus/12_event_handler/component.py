"""Button with an on_click event handler."""

import reflex as rx


class S(rx.State):
    count: int = 0

    @rx.event
    def increment(self):
        self.count += 1


ROUTE = "/events"
IDENT = "Events"


def build():
    return rx.box(rx.text("counter"), on_click=S.increment)
