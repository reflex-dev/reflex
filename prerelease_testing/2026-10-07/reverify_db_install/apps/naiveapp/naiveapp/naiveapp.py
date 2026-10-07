"""App written for naive datetimes, as reflex[db] users did before sqlmodel 0.0.45 (UTC default):
plain `datetime` column, datetime.now() writes, naive comparisons."""

from datetime import datetime, timedelta

import reflex as rx
import sqlmodel


class Event(rx.Model, table=True):
    title: str
    at: datetime


class State(rx.State):
    events: list[Event] = []
    ages: list[str] = []
    status: str = "idle"

    @rx.event
    def add(self):
        with rx.session() as s:
            s.add(Event(title="naive", at=datetime.now()))
            s.commit()
        self.status = "added"
        return State.load

    @rx.event
    def load(self):
        with rx.session() as s:
            rows = list(s.exec(sqlmodel.select(Event).order_by(Event.id)).all())
        self.events = rows
        now = datetime.now()
        self.ages = [
            f"{e.id}:{e.title}:{'recent' if now - e.at < timedelta(days=1) else 'old'}"
            for e in rows
        ]
        self.status = f"loaded {len(rows)}"


def row(e: Event):
    return rx.hstack(rx.text(e.id), rx.text(e.title), rx.text(e.at.to(str), class_name="raw"), class_name="post")


def index():
    return rx.vstack(
        rx.heading("naive app"),
        rx.button("Add", on_click=State.add, id="add"),
        rx.text(State.status, id="status"),
        rx.vstack(rx.foreach(State.events, row), id="posts"),
        rx.vstack(rx.foreach(State.ages, lambda a: rx.text(a, class_name="age")), id="ages"),
    )


app = rx.App()
app.add_page(index, on_load=State.load)
