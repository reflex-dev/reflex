"""One page; with the proxy mounted, GET backend:/ should serve it."""

import reflex as rx

import reflex_enterprise as rxe


def index() -> rx.Component:
    return rx.text("single-port page", id="t")


app = rxe.App()
app.add_page(index)
