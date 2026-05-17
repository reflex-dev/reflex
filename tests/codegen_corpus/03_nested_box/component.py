"""Corpus fixture: deeply nested boxes."""

import reflex as rx

ROUTE = "/nested"
IDENT = "Nested"


def build():
    return rx.box(rx.box(rx.box(rx.text("inner most"))))
