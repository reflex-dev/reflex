"""State var rendered as a Bare."""

import reflex as rx


class S(rx.State):
    name: str = "world"


ROUTE = "/state_var"
IDENT = "StateVar"


def build():
    return rx.text(S.name)
