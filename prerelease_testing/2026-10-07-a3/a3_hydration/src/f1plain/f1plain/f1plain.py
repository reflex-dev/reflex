"""F1 verifier minimal app: ONE state, client storage only, deterministic defaults (no default_factory, no env)."""

import reflex as rx

import os as _os_guard
assert f"/scratchpad/envs/{_os_guard.environ['RVH_VENV']}/" in rx.__file__, (_os_guard.environ.get("RVH_VENV"), rx.__file__)


class Prefs(rx.State):
    theme: str = rx.LocalStorage("light", name="p_theme")
    consent: str = rx.Cookie("unset", name="p_consent")
    tab: str = rx.SessionStorage("x", name="p_tab")

    @rx.event
    def go_dark(self):
        self.theme = "dark"


def index() -> rx.Component:
    return rx.vstack(
        rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd-flag"),
        rx.text(Prefs.theme, id="theme"),
        rx.text(Prefs.consent, id="consent"),
        rx.text(Prefs.tab, id="tab"),
        rx.button("dark", on_click=Prefs.go_dark, id="set-dark"),
    )


app = rx.App()
app.add_page(index)
