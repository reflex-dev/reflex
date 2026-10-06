"""Minimal repro: an @rx.memo component with a parameter named `tag`."""

import reflex as rx

assert "/scratchpad/envs/dataeditor_components-" in rx.__file__, rx.__file__


class S(rx.State):
    label: str = "hello"


@rx.memo
def chip(tag: rx.Var[str]) -> rx.Component:
    return rx.badge(tag)


def index() -> rx.Component:
    # A state var passed to the memo makes it stateful, so the compiler auto-memoizes it.
    return rx.box(chip(tag=S.label), chip(tag="static"))


app = rx.App()
app.add_page(index)
