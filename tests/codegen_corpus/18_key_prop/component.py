"""Foreach body uses the item value as a `key` prop."""

import reflex as rx


class S(rx.State):
    items: list[str] = []


ROUTE = "/key_prop"
IDENT = "KeyProp"


def build():
    return rx.foreach(S.items, lambda item: rx.box(item, key=item))
