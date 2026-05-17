"""Computed var displayed in a box."""

import reflex as rx


class S(rx.State):
    a: int = 1
    b: int = 2

    @rx.var
    def total(self) -> int:
        return self.a + self.b


ROUTE = "/computed"
IDENT = "Computed"


def build():
    return rx.text(S.total)
