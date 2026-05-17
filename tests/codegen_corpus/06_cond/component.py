"""Corpus fixture: rx.cond against a state Var."""

import reflex as rx


class CondState(rx.State):
    logged_in: bool = False


ROUTE = "/cond"
IDENT = "Cond"


def build():
    return rx.cond(CondState.logged_in, rx.text("welcome back"), rx.text("please log in"))
