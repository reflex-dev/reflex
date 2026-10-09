"""Minimal rx.Model app for the N-001 CLI check: db init / makemigrations / migrate, then a CRUD page."""

import datetime

import reflex as rx
import sqlmodel


class Note(rx.Model, table=True):
    text: str
    created: datetime.datetime = sqlmodel.Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class NoteState(rx.State):
    notes: list[str] = []

    @rx.event
    def add(self):
        with rx.session() as s:
            s.add(Note(text=f"note {len(self.notes) + 1}"))
            s.commit()
        self.load()

    @rx.event
    def load(self):
        with rx.session() as s:
            self.notes = [n.text for n in s.exec(sqlmodel.select(Note)).all()]


def index():
    return rx.vstack(
        rx.button("add", id="add", on_click=NoteState.add),
        rx.text(NoteState.notes.length(), id="count"),
        rx.foreach(NoteState.notes, rx.text),
        on_mount=NoteState.load,
    )


app = rx.App()
app.add_page(index)
