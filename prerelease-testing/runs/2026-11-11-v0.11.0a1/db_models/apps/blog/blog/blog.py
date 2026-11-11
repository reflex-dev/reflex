"""New-style blog app: async SQLAlchemy sessions per the 0.11 docs."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

import reflex as rx

from .db import Session
from .models import Author, Post, Role, Tag


class BlogState(rx.State):
    authors: list[Author] = []
    posts: list[Post] = []
    msg: str = ""

    @rx.event
    async def load(self):
        async with Session() as session:
            self.authors = (await session.scalars(select(Author).order_by(Author.id))).all()
            self.posts = (
                await session.scalars(
                    select(Post).options(selectinload(Post.author), selectinload(Post.tags)).order_by(Post.id)
                )
            ).all()

    @rx.event
    async def add_author(self, form: dict):
        async with Session() as session:
            session.add(
                Author(
                    name=form["name"],
                    email=form.get("email") or None,
                    role=Role(form.get("role") or "writer"),
                    profile={"city": form.get("city", ""), "langs": ["en", "fr"]},
                )
            )
            try:
                await session.commit()
            except IntegrityError as e:
                await session.rollback()
                self.msg = f"error: {type(e).__name__}"
                return
        self.msg = f"added author {form['name']}"
        return BlogState.load

    @rx.event
    async def add_post(self, form: dict):
        async with Session() as session:
            author = await session.scalar(select(Author).where(Author.name == form["author"]))
            if author is None:
                self.msg = "no such author"
                return
            tags = []
            for t in [x.strip() for x in form.get("tags", "").split(",") if x.strip()]:
                tags.append(await session.scalar(select(Tag).where(Tag.name == t)) or Tag(name=t))
            session.add(Post(title=form["title"], body=form.get("body", ""), author_id=author.id, tags=tags))
            await session.commit()
        self.msg = f"added post {form['title']}"
        return BlogState.load


class DetailState(BlogState):
    post: Post | None = None

    @rx.event
    async def load_post(self):
        pid = int(self.router.url.query_parameters.get("pid") or self.router.page.params.get("pid", 0) or 0)
        async with Session() as session:
            self.post = await session.scalar(
                select(Post).where(Post.id == pid).options(selectinload(Post.author), selectinload(Post.tags))
            )

    @rx.event
    async def bump(self):
        async with Session() as session:
            p = await session.get(Post, self.post.id)
            p.views += 1
            await session.commit()
        return DetailState.load_post


def post_row(p: Post):
    return rx.hstack(
        rx.link(p.title, href="/post/" + p.id.to_string(), class_name="post-link"),
        rx.text(" by ", p.author.name, class_name="post-author"),
        rx.foreach(p.tags, lambda t: rx.badge(t.name, class_name="tag")),
        class_name="post-row",
    )


def index():
    return rx.vstack(
        rx.heading("Blog (new style)"),
        rx.text(BlogState.msg, id="msg"),
        rx.form(
            rx.input(name="name", placeholder="author name", id="a_name"),
            rx.input(name="email", placeholder="email", id="a_email"),
            rx.input(name="city", placeholder="city", id="a_city"),
            rx.input(name="role", placeholder="role", id="a_role"),
            rx.button("Add author", type="submit", id="add_author"),
            on_submit=BlogState.add_author,
            reset_on_submit=True,
        ),
        rx.form(
            rx.input(name="author", placeholder="author", id="p_author"),
            rx.input(name="title", placeholder="title", id="p_title"),
            rx.input(name="body", placeholder="body", id="p_body"),
            rx.input(name="tags", placeholder="tags (comma)", id="p_tags"),
            rx.button("Add post", type="submit", id="add_post"),
            on_submit=BlogState.add_post,
            reset_on_submit=True,
        ),
        rx.heading("Authors", size="4"),
        rx.foreach(
            BlogState.authors,
            lambda a: rx.text(a.name, " <", a.email, "> ", a.role, " ", a.profile.to(dict)["city"], class_name="author-row"),
        ),
        rx.heading("Posts", size="4"),
        rx.foreach(BlogState.posts, post_row),
    )


def detail():
    return rx.cond(
        DetailState.post,
        rx.vstack(
            rx.heading(DetailState.post.title, id="d_title"),
            rx.text(DetailState.post.body, id="d_body"),
            rx.text("author: ", DetailState.post.author.name, " role: ", DetailState.post.author.role, id="d_author"),
            rx.text("created: ", DetailState.post.created_at, id="d_created"),
            rx.text("joined: ", DetailState.post.author.joined_at, id="d_joined"),
            rx.text("profile city: ", DetailState.post.author.profile.to(dict)["city"], id="d_city"),
            rx.hstack(rx.foreach(DetailState.post.tags, lambda t: rx.badge(t.name, class_name="dtag")), id="d_tags"),
            rx.text("views: ", DetailState.post.views, id="d_views"),
            rx.button("bump", on_click=DetailState.bump, id="bump"),
            rx.link("back", href="/"),
        ),
        rx.text("loading or missing", id="d_missing"),
    )


app = rx.App()
app.add_page(index, on_load=BlogState.load)
app.add_page(detail, route="/post/[pid]", on_load=DetailState.load_post)
