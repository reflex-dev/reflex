"""Core-only (no enterprise) check: does a State.get_delta override see boot-time client storage?

Prefs.theme is a synced LocalStorage var. Prefs.get_delta logs every value of it that passes
through a delta ("GET_DELTA_SAW theme=..."); the server log shows whether the boot sequence
(0.9.12: hydrate + update_vars_internal; 0.10: hydrate_and_load) routes the browser's value
through the override.
"""

import reflex as rx
from reflex.constants.state import FIELD_MARKER


class Prefs(rx.State):
    theme: str = rx.LocalStorage("light", sync=True)

    @rx.state._override_base_method  # private decorator, the same one reflex-enterprise uses
    def get_delta(self):
        delta = super().get_delta()
        sub = delta.get(self.get_full_name()) or {}
        if "theme" + FIELD_MARKER in sub:
            print(f"GET_DELTA_SAW theme={sub['theme' + FIELD_MARKER]!r}", flush=True)
        return delta

    @rx.event
    def set_dark(self):
        self.theme = "dark"


def index():
    return rx.vstack(
        rx.text("theme=", rx.text.span(Prefs.theme, id="theme")),
        rx.button("dark", on_click=Prefs.set_dark, id="dark"),
        rx.link("other", href="/other", id="other"),
    )


def other():
    return rx.text("other page ", rx.text.span(Prefs.theme, id="theme2"))


app = rx.App()
app.add_page(index)
app.add_page(other, route="/other")
