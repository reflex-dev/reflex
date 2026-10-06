"""Minimal real-world app: an rx.Model with a plain `created_at: datetime`, a handler that
compares it with datetime.now(timezone.utc) (as sqlmodel>=0.0.45 forces apps to write), and a
handler that writes a naive datetime.now() (how pre-0.0.45 code is commonly written)."""

from datetime import datetime, timedelta, timezone

import reflex as rx
import sqlmodel


class Post(rx.Model, table=True):
    title: str
    created_at: datetime


class State(rx.State):
    posts: list[Post] = []
    ages: list[str] = []
    status: str = "idle"

    @rx.event
    def add_aware(self):
        with rx.session() as s:
            s.add(Post(title="aware", created_at=datetime.now(timezone.utc)))
            s.commit()
        self.status = "added aware"
        return State.load

    @rx.event
    def add_naive(self):
        with rx.session() as s:
            s.add(Post(title="naive", created_at=datetime.now()))
            s.commit()
        self.status = "added naive"
        return State.load

    @rx.event
    def load(self):
        with rx.session() as s:
            rows = list(s.exec(sqlmodel.select(Post).order_by(Post.id)).all())
        self.posts = rows  # assigned first: still sent to the client if the comparison below raises
        now = datetime.now(timezone.utc)
        self.ages = [
            f"{p.id}:{p.title}:{'recent' if now - p.created_at < timedelta(days=1) else 'old'}"
            for p in rows
        ]
        self.status = f"loaded {len(rows)}"


def post_row(p: Post):
    return rx.hstack(
        rx.text(p.id),
        rx.text(p.title),
        rx.text(p.created_at.to(str), class_name="raw"),
        rx.moment(p.created_at.to(str), format="YYYY-MM-DD HH:mm Z", class_name="local"),
        class_name="post",
    )


def index():
    return rx.vstack(
        rx.heading("dt app"),
        rx.hstack(
            rx.button("Add aware", on_click=State.add_aware, id="add_aware"),
            rx.button("Add naive", on_click=State.add_naive, id="add_naive"),
            rx.button("Load", on_click=State.load, id="load"),
        ),
        rx.text(State.status, id="status"),
        rx.vstack(rx.foreach(State.posts, post_row), id="posts"),
        rx.vstack(rx.foreach(State.ages, lambda a: rx.text(a, class_name="age")), id="ages"),
    )


app = rx.App()
app.add_page(index, on_load=State.load)
