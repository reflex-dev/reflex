"""Serializer (#7756) end-to-end app."""

import asyncio

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

import reflex as rx

from .db import ExpiringSession, Session
from .models import Flag, Post, Tag, User

FULL = (selectinload(Post.user), selectinload(Post.tags), selectinload(Post.flags).selectinload(Flag.user))


class S(rx.State):
    posts: list[Post] = []
    user: User | None = None
    bg_posts: list[Post] = []
    sync_posts: list[Post] = []
    as_posts: list[Post] = []
    expired_user: User | None = None
    msg: str = ""

    @rx.var
    def top_post(self) -> Post | None:
        return self.posts[0] if self.posts else None

    @rx.var
    def titles(self) -> list[str]:
        return [p.title for p in self.posts]

    @rx.event
    async def seed(self):
        async with Session() as session:
            if await session.scalar(select(func.count(User.id))):
                self.msg = "already seeded"
                return S.load
            alice = User(username="alice", email="a@x.io")
            bob = User(username="bob", email="b@x.io")
            news, misc = Tag(name="news"), Tag(name="misc")
            session.add_all([alice, bob, news, misc])
            await session.flush()
            p1 = Post(title="First", body="b1", user_id=alice.id, tags=[news, misc])
            p2 = Post(title="Second", body="b2", user_id=bob.id, tags=[news])
            session.add_all([p1, p2])
            await session.flush()
            session.add_all([Flag(post_id=p1.id, user_id=bob.id, message="spam?"), Flag(post_id=p1.id, user_id=alice.id, message="ok")])
            await session.commit()
        self.msg = "seeded"
        return S.load

    @rx.event
    async def load(self):
        async with Session() as session:
            self.posts = (await session.scalars(select(Post).options(*FULL).order_by(Post.id))).all()
            self.user = await session.scalar(select(User).where(User.username == "alice"))

    @rx.event
    async def add_post(self, form: dict):
        async with Session() as session:
            session.add(Post(title=form["title"], body="new", user_id=self.user.id))
            await session.commit()
        return S.load

    @rx.event
    def mutate_in_state(self):
        # mutate a model instance held in state, no DB
        self.posts[0].title = "MUTATED"
        self.user.username = "alice-mutated"

    @rx.event
    def append_tag_in_state(self):
        self.posts[0].tags.append(Tag(name="appended"))

    @rx.event
    async def rename_db(self):
        async with Session() as session:
            p = await session.get(Post, self.posts[0].id)
            p.title = p.title + "!"
            await session.commit()
        return S.load

    @rx.event(background=True)
    async def bg_load(self):
        await asyncio.sleep(0.2)
        async with Session() as session:
            rows = (await session.scalars(select(Post).options(*FULL).order_by(Post.id))).all()
        async with self:
            self.bg_posts = rows
            self.msg = f"bg loaded {len(rows)}"

    @rx.event
    def sync_load(self):
        with rx.session() as session:
            self.sync_posts = list(session.scalars(select(Post).order_by(Post.id)).all())
            # touch a lazy relationship inside the open sync session
            self.msg = "sync lazy user: " + self.sync_posts[0].user.username

    @rx.event
    async def asession_load(self):
        async with rx.asession() as session:
            self.as_posts = (await session.scalars(select(Post).options(*FULL).order_by(Post.id))).all()
        self.msg = f"asession loaded {len(self.as_posts)}"

    @rx.event
    async def expired_load(self):
        async with ExpiringSession() as session:
            u = await session.scalar(select(User).where(User.username == "bob"))
            u.email = "bob@new.io"
            await session.commit()
            self.expired_user = u
        self.msg = "expired loaded"


class Unloaded(rx.State):
    posts: list[Post] = []

    @rx.event
    async def load(self):
        async with Session() as session:
            self.posts = (await session.scalars(select(Post).order_by(Post.id))).all()


class Detail(rx.State):
    post: Post | None = None

    @rx.event
    async def load(self):
        pid = int(self.router.page.params.get("pid", 0) or 0)
        async with Session() as session:
            self.post = await session.scalar(select(Post).where(Post.id == pid).options(*FULL))


def post_card(post: Post):
    return rx.vstack(
        rx.text(post.title, " by ", post.user.username, " / ", post.user.nick.upper(), class_name="p-head"),
        rx.text(post.flags.length(), " flags", class_name="p-nflags"),
        rx.foreach(post.flags, lambda f: rx.text(f.message, " from ", f.user.username, class_name="p-flag")),
        rx.hstack(rx.foreach(post.tags, lambda t: rx.badge(t.name, class_name="p-tag"))),
        class_name="post",
    )


def simple_list(var, cls):
    return rx.foreach(var, lambda p: rx.text(p.title, " | ", p.user.username, class_name=cls))


def index():
    return rx.vstack(
        rx.text(S.msg, id="msg"),
        rx.hstack(
            rx.button("seed", on_click=S.seed, id="seed"),
            rx.button("load", on_click=S.load, id="load"),
            rx.button("mutate", on_click=S.mutate_in_state, id="mutate"),
            rx.button("append tag", on_click=S.append_tag_in_state, id="append"),
            rx.button("rename db", on_click=S.rename_db, id="rename"),
            rx.button("bg", on_click=S.bg_load, id="bg"),
            rx.button("sync", on_click=S.sync_load, id="sync"),
            rx.button("asession", on_click=S.asession_load, id="asess"),
            rx.button("expired", on_click=S.expired_load, id="expired"),
        ),
        rx.form(rx.input(name="title", id="new_title"), rx.button("add", type="submit", id="add"), on_submit=S.add_post, reset_on_submit=True),
        rx.text("user: ", S.user.username, " nick upper: ", S.user.nick.upper(), " hybrid: [", S.user.upper_name, "] name_len: [", S.user.name_len, "]", id="user"),
        rx.text("top: ", S.top_post.title, " by ", S.top_post.user.username, id="top"),
        rx.text("titles: ", S.titles.join(","), id="titles"),
        rx.foreach(S.posts, post_card),
        rx.text("bg:", id="bg_h"), simple_list(S.bg_posts, "bg-row"),
        rx.text("sync:", id="sync_h"), simple_list(S.sync_posts, "sync-row"),
        rx.text("asession:", id="as_h"), simple_list(S.as_posts, "as-row"),
        rx.text("expired user: [", S.expired_user.username, "] [", S.expired_user.email, "]", id="exp"),
        rx.link("detail 1", href="/detail/1", id="to_detail"),
    )


def unloaded_soft():
    return rx.vstack(
        rx.text("soft page", id="soft"),
        rx.foreach(Unloaded.posts, lambda p: rx.text(p.title, " by [", p.user.username, "]", class_name="u-row")),
    )


def unloaded_hard():
    return rx.vstack(
        rx.text("hard page", id="hard"),
        rx.foreach(Unloaded.posts, lambda p: rx.text(p.title, " flags ", p.flags.length(), class_name="u-row")),
    )


def detail():
    return rx.cond(
        Detail.post,
        rx.vstack(
            rx.heading(Detail.post.title, id="d_title"),
            rx.text(Detail.post.user.username, id="d_user"),
            rx.foreach(Detail.post.tags, lambda t: rx.badge(t.name, class_name="d-tag")),
        ),
        rx.text("none", id="d_none"),
    )


app = rx.App()
app.add_page(index, on_load=S.load)
app.add_page(unloaded_soft, route="/unloaded_soft", on_load=Unloaded.load)
app.add_page(unloaded_hard, route="/unloaded_hard", on_load=Unloaded.load)
app.add_page(detail, route="/detail/[pid]", on_load=Detail.load)
