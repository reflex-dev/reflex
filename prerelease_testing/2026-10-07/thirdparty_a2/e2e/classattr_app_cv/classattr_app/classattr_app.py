"""Minimal re-derived app for claims A and B (identical source for reflex 0.9.12 and 0.10.0a1; ClassVar variant: the documented workaround for class constants)."""

from typing import ClassVar

import reflex as rx


class ConstState(rx.State):
    """Unannotated backend class constant read at class level while building the page (claim A)."""

    _LABEL: ClassVar[str] = "label-const"


class Cfg(rx.State):
    """A declared backend var configured by class-level assignment at import time (claim B)."""

    _key: str | None = None
    shown: str = ""
    log: list[str] = []

    @rx.event
    def show(self):
        self.shown = f"key={self._key!r}"
        self.log.append(self.shown)

    @rx.event
    def set_instance(self):
        self._key = "set-on-instance"

    @rx.event
    def do_reset(self):
        self.reset()
        self.log.append("reset-done")


Cfg._key = "sk_live"  # reflex-clerk style: ClerkState._secret_key = props["secret_key"]


class Counter(rx.ComponentState):
    """ComponentState reading a backend class constant in get_component (claim A)."""

    count: int = 0
    _step: ClassVar[int] = 5

    @rx.event
    def incr(self):
        self.count += self._step

    @classmethod
    def get_component(cls, **props):
        return rx.hstack(
            rx.button(f"+{cls._step}", on_click=cls.incr, id="cs_btn"),
            rx.text(cls.count, id="cs_count"),
        )


def index():
    return rx.vstack(
        rx.text(f"label={ConstState._LABEL}", id="fstring_label"),
        Counter.create(),
        rx.button("show", id="show", on_click=Cfg.show),
        rx.button("set_instance", id="set_instance", on_click=Cfg.set_instance),
        rx.button("reset", id="reset", on_click=Cfg.do_reset),
        rx.text(Cfg.shown, id="shown"),
        rx.text(Cfg.log.join(" | "), id="log"),
    )


app = rx.App()
app.add_page(index)
