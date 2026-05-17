"""Corpus fixture: rx.match against a state Var."""

import reflex as rx


class MatchState(rx.State):
    mode: str = "x"


ROUTE = "/match"
IDENT = "MatchPage"


def build():
    return rx.match(
        MatchState.mode,
        ("a", rx.text("alpha")),
        ("b", rx.text("beta")),
        rx.text("default"),
    )
