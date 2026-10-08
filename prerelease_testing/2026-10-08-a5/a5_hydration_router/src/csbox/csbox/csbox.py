"""reverify_hydration: ComponentState with a browser-storage var whose per-instance default is set in
get_component via the #7461 class-default assignment (`cls.pref = ...`). Does the instance still persist
to localStorage, and does hydration restore it?"""
import os

import reflex as rx

assert f"/scratchpad/envs/{os.environ['RVH_VENV']}/" in rx.__file__, (os.environ.get("RVH_VENV"), rx.__file__)


class Box(rx.ComponentState):
    pref: str = rx.LocalStorage("light", name="box_pref")

    @rx.event
    def choose(self, v: str):
        self.pref = v

    @classmethod
    def get_component(cls, *children, tag="x", initial=None, mode="none", **props):
        if mode == "plain":
            cls.pref = initial
        elif mode == "storage":
            cls.pref = rx.LocalStorage(initial, name=f"box_pref_{tag}")
        return rx.hstack(
            rx.text(tag, ":"),
            rx.text(cls.pref, id=f"pref-{tag}"),
            rx.button(f"choose {tag}", on_click=cls.choose(f"user-{tag}"), id=f"choose-{tag}"),
        )


def index() -> rx.Component:
    a = Box.create(tag="none", mode="none")
    b = Box.create(tag="plain", initial="dark", mode="plain")
    c = Box.create(tag="storage", initial="dark", mode="storage")
    return rx.vstack(
        rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd-flag"),
        a, b, c,
    )


app = rx.App()
app.add_page(index)
