"""State var in a Box that also has a literal prop."""

import reflex as rx


class S(rx.State):
    count: int = 0


ROUTE = "/state_in_box"
IDENT = "StateInBox"


def build():
    return rx.box(S.count, class_name="counter")
