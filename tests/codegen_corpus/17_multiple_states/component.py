"""Two state classes used in the same component tree."""

import reflex as rx


class A(rx.State):
    title: str = "page title"


class B(rx.State):
    body: str = "page body"


ROUTE = "/multi_state"
IDENT = "MultiState"


def build():
    return rx.box(rx.text(A.title), rx.text(B.body))
