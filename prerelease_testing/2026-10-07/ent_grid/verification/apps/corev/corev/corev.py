"""Core-only (no enterprise) fixture: does a render-time reader of window.__reflex that
consumes an UNCHANGED substate ever see window.__reflex after the boot hydrate?"""

import reflex as rx

from .probe import reflex_probe


class Untouched(rx.State):
    """Never modified during boot."""

    cols: list[str] = ["a", "b"]
    n: int = 0

    @rx.event
    def bump(self):
        self.n += 1


class Touched(rx.State):
    """Modified by the index page's on_load."""

    value: str = "init"

    @rx.event
    def on_load_set(self):
        self.value = "loaded"


class Other(rx.State):
    """Unrelated substate changed by a button."""

    x: int = 0

    @rx.event
    def bump(self):
        self.x += 1


def index() -> rx.Component:
    return rx.vstack(
        rx.heading("corev index", id="heading"),
        reflex_probe(label="untouched", value=Untouched.cols),
        reflex_probe(label="untouched_n", value=Untouched.n),
        reflex_probe(label="touched", value=Touched.value),
        reflex_probe(label="other", value=Other.x),
        reflex_probe(label="literal", value="lit"),
        rx.button("bump other", on_click=Other.bump, id="bump-other"),
        rx.button("bump untouched", on_click=Untouched.bump, id="bump-untouched"),
        rx.link("to second", href="/second", id="to-second"),
    )


def second() -> rx.Component:
    return rx.vstack(
        rx.heading("corev second", id="heading"),
        reflex_probe(label="second_untouched", value=Untouched.cols),
        rx.link("to index", href="/", id="to-index"),
    )


class Dyn(rx.State):
    """Dynamic component (state var of Component type) evaluated through window.__reflex."""

    label: str = "dynamic-ok"

    @rx.var
    def comp(self) -> rx.Component:
        return rx.badge(self.label, id="dyn-badge")


def dyn() -> rx.Component:
    return rx.vstack(
        rx.heading("corev dyn", id="heading"),
        rx.box(Dyn.comp, id="dyn-wrap"),
        reflex_probe(label="dyn_label", value=Dyn.label),
    )


app = rx.App()
app.add_page(index, route="/", on_load=Touched.on_load_set)
app.add_page(second, route="/second")
app.add_page(dyn, route="/dyn")
