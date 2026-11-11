"""Minimal module for issue 2: how a type checker sees bare and parenthesised @rx.event handlers."""
from typing import reveal_type

import reflex as rx


class S(rx.State):
    n: int = 0

    @rx.event
    def bare(self, x: int):
        self.n += x

    @rx.event()
    def paren(self, x: int):
        self.n += x

    @rx.event
    def caller(self):
        reveal_type(self.bare)


reveal_type(S.bare)
reveal_type(S.paren)
reveal_type(S.bare(1))
S.bare("not an int")  # should be an error
S.bare(1, 2, 3)  # should be an error
rx.input(on_change=S.bare)  # int handler on a str trigger: should be an error
