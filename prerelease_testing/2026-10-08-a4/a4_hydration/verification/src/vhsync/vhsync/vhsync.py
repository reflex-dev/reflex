"""verify_hydration: minimal sync=True LocalStorage app (independent of the explorer's bootecho/syncstamp).

/             no on_load. Prefs.theme = rx.LocalStorage("light", name="vh_theme", sync=True); buttons change it
              (#toggle light<->dark, #pick-red/green/blue set a fixed value). A3-11 surface.
/withload     same UI, plus an on_load that does NOT touch the synced var (does the boot echo also hit on_load pages?).
/doc/[slug]   on_load stamps Recent.last_doc = slug (sync=True LocalStorage "vh_last_doc"): a "recently viewed"
              var; tabs restored on different docs write different values at once. A3-12 surface.
"""

import os
import time

import reflex as rx

assert f"/scratchpad/envs/{os.environ['VH_VENV']}/" in rx.__file__, (os.environ.get("VH_VENV"), rx.__file__)


class Prefs(rx.State):
    theme: str = rx.LocalStorage("light", name="vh_theme", sync=True)

    @rx.event
    def toggle(self):
        self.theme = "dark" if self.theme != "dark" else "light"

    @rx.event
    def pick(self, v: str):
        self.theme = v

    @rx.event
    def bump(self):
        # A fresh value per click (the explorer's s1..s5 shape).
        self.theme = f"v{time.time_ns() // 1_000_000 % 1_000_000}"

    @rx.event
    def noop_load(self):
        pass


class Recent(rx.State):
    last_doc: str = rx.LocalStorage("", name="vh_last_doc", sync=True)

    @rx.event
    def stamp(self):
        self.last_doc = self.router.page.params.get("slug", "?")


def ui():
    return rx.vstack(
        rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd-flag"),
        rx.text(Prefs.theme, id="theme"),
        rx.text(Recent.last_doc, id="last-doc"),
        rx.hstack(
            rx.button("toggle", on_click=Prefs.toggle, id="toggle"),
            rx.button("red", on_click=Prefs.pick("red"), id="pick-red"),
            rx.button("green", on_click=Prefs.pick("green"), id="pick-green"),
            rx.button("blue", on_click=Prefs.pick("blue"), id="pick-blue"),
            rx.button("bump", on_click=Prefs.bump, id="bump"),
        ),
    )


def index():
    return ui()


def withload():
    return ui()


def doc():
    return ui()


app = rx.App()
app.add_page(index, route="/")
app.add_page(withload, route="/withload", on_load=Prefs.noop_load)
app.add_page(doc, route="/doc/[slug]", on_load=Recent.stamp)
