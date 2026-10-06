"""User forgot to import Item (common typo) under postponed annotations."""

from __future__ import annotations

import reflex as rx


class TodoState(rx.State):
    """`Item` is never imported."""

    items: list[Item] = []  # noqa: F821
    title: str = ""


def index() -> rx.Component:
    return rx.text(TodoState.title)


app = rx.App()
app.add_page(index)
