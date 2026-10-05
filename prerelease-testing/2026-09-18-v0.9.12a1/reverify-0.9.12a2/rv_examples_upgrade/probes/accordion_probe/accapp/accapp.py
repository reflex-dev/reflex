"""Minimal repro: rx.accordion.root(collapsible=True, type="multiple") as used by
reflex-examples/form-designer's responses page."""

import reflex as rx


def index() -> rx.Component:
    return rx.vstack(
        rx.heading("accordion collapsible probe"),
        rx.accordion.root(
            rx.accordion.item(header="A", content="content A", value="a"),
            rx.accordion.item(header="B", content="content B", value="b"),
            collapsible=True,
            type="multiple",
            variant="outline",
            radius="small",
            id="multi-root",
        ),
        rx.accordion.root(
            rx.accordion.item(header="C", content="content C", value="c"),
            collapsible=True,
            type="single",
            id="single-root",
        ),
        rx.accordion.root(
            rx.accordion.item(header="D", content="content D", value="d"),
            type="multiple",
            id="nocollapsible-root",
        ),
        spacing="4",
        padding="2em",
    )


app = rx.App()
app.add_page(index)
