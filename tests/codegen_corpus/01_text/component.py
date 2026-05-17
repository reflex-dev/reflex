"""Corpus fixture: bare text."""

import reflex as rx

ROUTE = "/text"
IDENT = "Text"


def build():
    return rx.text("hello corpus")
