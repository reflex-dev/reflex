"""Corpus fixture: a flex with multiple sibling children."""

import reflex as rx

ROUTE = "/multi"
IDENT = "Multi"


def build():
    return rx.flex(
        rx.text("alpha"),
        rx.text("beta"),
        rx.text("gamma"),
    )
