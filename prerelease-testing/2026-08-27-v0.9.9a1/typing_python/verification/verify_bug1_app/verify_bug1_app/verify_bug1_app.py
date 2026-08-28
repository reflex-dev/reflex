"""Minimal app: alias state var + uncalled alias-annotated handler on a trigger."""

from typing import Literal

import reflex as rx

type Key = Literal["a", "b"]


class S(rx.State):
    k: Key = "a"

    @rx.event
    def choose(self, value: Key):
        self.k = value


def index():
    return rx.vstack(rx.text(S.k), rx.input(on_change=S.choose))


app = rx.App()
app.add_page(index)
