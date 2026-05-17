"""Corpus fixture: a box with className and id props."""

import reflex as rx

ROUTE = "/styled"
IDENT = "Styled"


def build():
    return rx.box("styled content", class_name="main-panel", id="root")
