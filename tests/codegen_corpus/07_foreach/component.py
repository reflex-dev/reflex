"""Corpus fixture: rx.foreach over a state list."""

import reflex as rx


class ForeachState(rx.State):
    items: list[str] = []


ROUTE = "/list"
IDENT = "List"


def build():
    return rx.flex(
        rx.foreach(ForeachState.items, lambda item: rx.text(item)),
    )
