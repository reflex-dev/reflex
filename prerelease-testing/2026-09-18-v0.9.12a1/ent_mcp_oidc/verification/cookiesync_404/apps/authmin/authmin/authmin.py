"""AuthPlugin control app: does the cookie-sync route exist from startup?"""

import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.auth.cookie import HTTPCookie


class PubState(rx.State):
    hits: int = 0

    @rxe.event(auth=False)
    def bump(self):
        self.hits += 1


def index() -> rx.Component:
    return rx.vstack(
        rx.text(PubState.hits, id="hits"),
        rx.button("bump", on_click=PubState.bump, id="bump"),
        rx.button("Cookie Sync", on_click=HTTPCookie.sync(), id="sync"),
    )


app = rxe.App()
app.add_page(index, auth=False)
