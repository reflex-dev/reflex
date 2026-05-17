"""Corpus fixture: a box with a single text child."""

import reflex as rx

ROUTE = "/box"
IDENT = "Box"


def build():
    return rx.box(rx.text("inside box"))
