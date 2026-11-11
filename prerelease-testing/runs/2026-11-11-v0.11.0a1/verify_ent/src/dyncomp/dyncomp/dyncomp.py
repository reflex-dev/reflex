"""State holds Radix components (dynamic components) and a lambda-like var; one table."""

import reflex as rx
import sqlmodel


class Item(rx.Model, table=True):
    name: str = ""


class S(rx.State):
    badge: rx.Component = rx.badge("hi", color_scheme="green")
    items: list[rx.Component] = [rx.callout("c", icon="info"), rx.hover_card.root(rx.hover_card.trigger(rx.text("t")), rx.hover_card.content(rx.text("x")))]
    n: int = 0

    @rx.var
    def comp(self) -> rx.Component:
        return rx.tooltip(rx.button(f"n={self.n}"), content="tip")


def index() -> rx.Component:
    return rx.vstack(S.badge, rx.foreach(S.items, lambda c: c), S.comp)


app = rx.App()
app.add_page(index)
