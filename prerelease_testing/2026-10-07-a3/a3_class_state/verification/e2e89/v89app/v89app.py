"""Verifier e2e app for a3_class_state-8 (None assigned to an Optional[str] storage var) and -9
(ComponentState instances sharing a named storage key)."""

import os
from typing import Optional

import reflex

assert f"/envs/{os.environ['EXPECT_VENV']}/" in reflex.__file__, reflex.__file__

import reflex as rx  # noqa: E402


class St(rx.State):
    opt: Optional[str] = rx.LocalStorage("d-opt", name="v_opt")
    plain: str = rx.LocalStorage("d-plain", name="v_plain")

    @rx.event
    def set_both(self):
        self.opt = "typed-opt"
        self.plain = "typed-plain"


# Module-level configuration (finding 8): None for the Optional var, a str for the control.
St.opt = None
St.plain = "cfg-plain"


class Box(rx.ComponentState):
    pref: str = rx.LocalStorage("light", name="v_box_pref")

    @rx.event
    def choose(self, value: str):
        self.pref = value

    @classmethod
    def get_component(cls, tag: str, initial: str = "", **props):
        if initial:
            cls.pref = initial
        return rx.hstack(
            rx.text(tag, ":"),
            rx.text(cls.pref, id=f"box-{tag}"),
            rx.button(f"choose {tag}", id=f"choose-{tag}", on_click=cls.choose(f"user-{tag}")),
        )


def index():
    return rx.vstack(
        rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd"),
        rx.text(St.opt, id="opt"),
        rx.text(St.plain, id="plain"),
        rx.button("set both", id="set", on_click=St.set_both),
        Box.create("a", initial="init-a"),
        Box.create("b", initial="init-b"),
        Box.create("c"),
    )


app = rx.App()
app.add_page(index)
