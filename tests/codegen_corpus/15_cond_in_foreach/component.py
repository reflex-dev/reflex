"""Nested combinators: rx.foreach with an rx.cond body."""

import reflex as rx


class S(rx.State):
    items: list[str] = []
    show_all: bool = True


ROUTE = "/cond_in_foreach"
IDENT = "CondInForeach"


def build():
    return rx.foreach(
        S.items,
        lambda item: rx.cond(S.show_all, rx.text(item), rx.fragment()),
    )
