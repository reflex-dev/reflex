"""STATE-36 / #7304: app package WITHOUT __init__.py (namespace package). Two states, on_load, click."""

import os

import reflex as rx

if os.environ.get("EXPECT_VENV"):  # venv guard
    assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__


class State(rx.State):
    """Root-level app state."""

    count: int = 0
    loaded: str = ""

    @rx.event
    def on_load(self):
        self.loaded = f"loaded pid={os.getpid()}"

    @rx.event
    def inc(self):
        self.count += 1


class Other(State):
    """A substate."""

    note: str = ""

    @rx.event
    def set_note(self):
        self.note = f"note {self.count}"


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("noinit", id="title"),
            rx.text("count: ", State.count, id="count"),
            rx.text("loaded: ", State.loaded, id="loaded"),
            rx.text("note: ", Other.note, id="note"),
            rx.text("hydrated: ", rx.cond(State.is_hydrated, "yes", "no"), id="hyd"),
            rx.button("inc", on_click=State.inc, id="inc"),
            rx.button("note", on_click=Other.set_note, id="notebtn"),
        )
    )


app = rx.App()
app.add_page(index, on_load=State.on_load)
