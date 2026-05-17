"""rx.foreach whose render_fn takes both (item, index)."""

import reflex as rx


class S(rx.State):
    items: list[str] = []


ROUTE = "/foreach_index"
IDENT = "ForeachIndex"


def build():
    return rx.foreach(S.items, lambda item, index: rx.text(item))
