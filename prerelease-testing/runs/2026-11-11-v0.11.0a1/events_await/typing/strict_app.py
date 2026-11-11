"""A plain 0.10-style app (no 0.11 features) for `pyright --strict`-style CI: what does upgrading change?"""
# pyright: strict

import reflex as rx


class S(rx.State):
    count: int = 0
    name: str = ""

    @rx.event
    def reset_count(self) -> None:
        self.count = 0

    @rx.event
    def add(self, amount: int) -> None:
        self.count += amount

    @rx.event
    def set_name(self, name: str) -> None:
        self.name = name

    @rx.event
    def both(self) -> None:
        self.add(1)
        self.set_name("x")


def index() -> rx.Component:
    return rx.vstack(
        rx.button("reset", on_click=S.reset_count),
        rx.button("add", on_click=S.add(1)),
        rx.input(on_change=S.set_name),
        rx.button("both", on_click=S.both),
    )


handler = S.add
spec = S.add(2)
