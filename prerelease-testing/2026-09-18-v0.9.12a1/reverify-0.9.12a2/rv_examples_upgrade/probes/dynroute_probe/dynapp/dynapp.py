"""Minimal repro: HTTP status of a dynamic route in prod (direct navigation)."""

import reflex as rx


class S(rx.State):
    @rx.var
    def item_id(self) -> str:
        return self.router.url.path.rsplit("/", 1)[-1]


def index() -> rx.Component:
    return rx.vstack(rx.heading("home"), rx.link("item 7", href="/item/7"))


def item() -> rx.Component:
    return rx.vstack(rx.heading("item page"), rx.text("id=", S.item_id, id="iid"))


app = rx.App()
app.add_page(index, route="/")
app.add_page(item, route="/item/[id]")
