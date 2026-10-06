"""Minimal repro: first page load persists client-storage DEFAULTS into the browser (0.10.0a1)."""

import os
import uuid

import reflex as rx

# Guard (added to the archived copy after the runs; functionally neutral): never import reflex from a checkout.
assert "/envs/alpha/" in rx.__file__ or "/envs/stable/" in rx.__file__, rx.__file__


class State(rx.State):
    # Client storage that the user never set.
    theme: str = rx.LocalStorage(os.environ.get("MINI_THEME_DEFAULT", "light"), name="mini_theme")
    consent: str = rx.Cookie("unset", name="mini_consent", max_age=3600)
    # Any per-process / per-instance default in the same state class makes the
    # backend send this state in full on the first hydrate.
    visitor_id: str = rx.field(default_factory=lambda: uuid.uuid4().hex)


def index() -> rx.Component:
    return rx.vstack(
        rx.text(rx.cond(State.is_hydrated, "H:yes", "H:no"), id="hyd-flag"),
        rx.text(State.theme, id="theme"),
        rx.text(State.consent, id="consent"),
        rx.text(State.visitor_id, id="vid"),
    )


app = rx.App()
app.add_page(index)
