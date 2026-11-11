"""Minimal repro: first page load persists client-storage DEFAULTS into the browser (0.10.0a1)."""

import os
import uuid

import reflex as rx

# Guard (added to the archived copy after the runs; functionally neutral): never import reflex from a checkout.
import os as _os_guard
assert f"/envs/{_os_guard.environ['RVH_VENV']}/" in rx.__file__, (_os_guard.environ.get("RVH_VENV"), rx.__file__)


class State(rx.State):
    # Client storage that the user never set.
    theme: str = rx.LocalStorage(os.environ.get("MINI_THEME_DEFAULT", "light"), name="mini_theme")
    consent: str = rx.Cookie("unset", name="mini_consent", max_age=3600)
    # Any per-process / per-instance default in the same state class makes the
    # backend send this state in full on the first hydrate.
    visitor_id: str = rx.field(default_factory=lambda: uuid.uuid4().hex)

    @rx.event
    def choose_theme(self, value: str):
        """A user choice (reverify_hydration addition): must be persisted."""
        self.theme = value
        self.consent = "granted"


def index() -> rx.Component:
    return rx.vstack(
        rx.text(rx.cond(State.is_hydrated, "H:yes", "H:no"), id="hyd-flag"),
        rx.text(State.theme, id="theme"),
        rx.text(State.consent, id="consent"),
        rx.text(State.visitor_id, id="vid"),
        rx.button("choose blue", on_click=State.choose_theme("blue"), id="choose-blue"),
    )


app = rx.App()
app.add_page(index)
