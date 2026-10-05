"""DB relationship / optional-import exploration app."""

import asyncio
import json
import sys

import reflex as rx
import sqlmodel
from sqlalchemy.orm import selectinload

from .models import Author, Book, BookTagLink, Tag

WATCH = {"sqlalchemy", "sqlmodel", "alembic", "pandas", "PIL", "plotly", "starlette_admin"}


def loaded_optional() -> list[str]:
    return sorted({m.split(".")[0] for m in sys.modules if m.split(".")[0] in WATCH})


# --- dynamically created model class with no __module__ (the "classes without module names" line)
DynBook = type("DynBook", (sqlmodel.SQLModel,), {"__annotations__": {"title": str}, "title": "dyn"})
try:
    del DynBook.__module__  # falls back to type's attribute; may raise
    DYN_MODULE = "deleted"
except Exception:  # noqa: BLE001
    try:
        DynBook.__module__ = None  # pyright: ignore
        DYN_MODULE = "None"
    except Exception as e:  # noqa: BLE001
        DYN_MODULE = f"unchanged ({e})"


class CustomSerModel(sqlmodel.SQLModel):
    """A direct SQLModel (not rx.Model) with a custom serializer override."""

    name: str = "direct"


@rx.serializer(to=dict)
def serialize_custom(m: CustomSerModel) -> dict:
    return {"CUSTOM": True, "name": m.name}


class State(rx.State):
    books: list[Book] = []
    authors: list[Author] = []
    single_book: Book | None = None
    log: list[str] = []
    modules_at_import: list[str] = []
    modules_now: list[str] = []
    dyn_serialized: str = ""
    custom_serialized: str = ""
    fields_dump: str = ""
    bg_result: str = ""
    seed_count: int = 0

    def on_load(self):
        self.modules_at_import = MODULES_AT_IMPORT
        self.modules_now = loaded_optional()

    def seed(self):
        with rx.session() as session:
            if session.exec(sqlmodel.select(Author)).first():
                self.log.append("already seeded")
                return
            a1 = Author(name="Ursula Le Guin", country="US")
            a2 = Author(name="Stanislaw Lem", country="PL")
            t1 = Tag(label="scifi")
            t2 = Tag(label="classic")
            session.add(a1)
            session.add(a2)
            session.add(t1)
            session.add(t2)
            session.commit()
            session.refresh(a1)
            session.refresh(a2)
            session.refresh(t1)
            session.refresh(t2)
            b1 = Book(title="The Dispossessed", year=1974, author_id=a1.id)
            b2 = Book(title="A Wizard of Earthsea", year=1968, author_id=a1.id)
            b3 = Book(title="Solaris", year=1961, author_id=a2.id)
            for b in (b1, b2, b3):
                session.add(b)
            session.commit()
            for b in (b1, b2, b3):
                session.refresh(b)
            session.add(BookTagLink(book_id=b1.id, tag_id=t1.id))
            session.add(BookTagLink(book_id=b1.id, tag_id=t2.id))
            session.add(BookTagLink(book_id=b3.id, tag_id=t1.id))
            session.commit()
            self.log.append("seeded 2 authors / 3 books / 2 tags")

    def load_books_sync(self):
        """with rx.session() + selectinload -> books with nested author and tags."""
        with rx.session() as session:
            self.books = session.exec(
                sqlmodel.select(Book)
                .options(selectinload(Book.author), selectinload(Book.tags))
                .order_by(Book.year)
            ).all()
        self.single_book = self.books[0] if self.books else None
        self.seed_count = len(self.books)
        self.log.append(f"sync loaded {len(self.books)} books")
        self.modules_now = loaded_optional()

    @rx.event
    async def load_authors_async(self):
        """async with rx.asession() + selectinload -> authors with nested books."""
        async with rx.asession() as session:
            result = await session.exec(
                sqlmodel.select(Author).options(selectinload(Author.books))
            )
            self.authors = result.all()
        self.log.append(f"async loaded {len(self.authors)} authors")
        self.modules_now = loaded_optional()

    def load_no_eager(self):
        """Load WITHOUT selectinload: relationship is unloaded -> DetachedInstanceError suppressed."""
        with rx.session() as session:
            self.books = session.exec(sqlmodel.select(Book).order_by(Book.year)).all()
        self.log.append(f"lazy(no eager) loaded {len(self.books)} books")

    def do_dyn(self):
        """Serialize the dynamically created class whose __module__ is None."""
        from reflex_base.utils import serializers as S

        with rx.session() as session:
            row = session.exec(
                sqlmodel.select(Book).options(selectinload(Book.author))
            ).first()
        try:
            dyn = DynBook(title="dyn")
            ser = S.serialize(dyn)
            mod = getattr(DynBook, "__module__", "<absent>")
            self.dyn_serialized = (
                f"OK mod_state={DYN_MODULE} module={mod!r} row={row.title if row else None} "
                f"-> {json.dumps(ser, default=str)[:160]}"
            )
        except Exception as e:  # noqa: BLE001
            self.dyn_serialized = f"{type(e).__name__}: {e}"

    def do_custom(self):
        from reflex_base.utils import serializers as S

        try:
            ser = S.serialize(CustomSerModel(name="hello"))
            self.custom_serialized = json.dumps(ser, default=str)
        except Exception as e:  # noqa: BLE001
            self.custom_serialized = f"{type(e).__name__}: {e}"

    def do_fields(self):
        with rx.session() as session:
            row = session.exec(
                sqlmodel.select(Book).options(selectinload(Book.author), selectinload(Book.tags))
            ).first()
            if row is None:
                self.fields_dump = "no rows"
                return
            parts = [
                f"__fields__={sorted(type(row).__fields__)}",
                f"dict_keys={sorted(row.dict())}",
                f"relationships={sorted(row.__sqlmodel_relationships__)}",
            ]
            try:
                from reflex_base.utils import serializers as S

                parts.append(f"serialize_keys={sorted(S.serialize(row))}")
            except Exception as e:  # noqa: BLE001
                parts.append(f"serialize FAILED {type(e).__name__}: {e}")
            self.fields_dump = " | ".join(parts)

    @rx.event(background=True)
    async def bg_load(self):
        """First DB touch inside a background task (cold-path exercise)."""
        await asyncio.sleep(0.1)
        async with self:
            self.bg_result = "starting"
        async with rx.asession() as session:
            result = await session.exec(
                sqlmodel.select(Book).options(selectinload(Book.author))
            )
            rows = result.all()
        async with self:
            self.books = rows
            self.single_book = rows[0] if rows else None
            self.bg_result = f"bg loaded {len(rows)} books; first author={rows[0].author.name if rows and rows[0].author else None}"
            self.modules_now = loaded_optional()

    def chain_all(self):
        """Event chain: seed -> sync load -> async load."""
        self.seed()
        yield State.load_books_sync
        yield State.load_authors_async


MODULES_AT_IMPORT = loaded_optional()


def book_row(b: Book) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.text(b.title, weight="bold"),
            rx.text("("),
            rx.text(b.year.to_string()),
            rx.text(")"),
            rx.text(" by "),
            # ObjectVar field access through a relationship
            rx.text(b.author.name, class_name="author-name"),
            rx.text(" / "),
            rx.text(b.author.country, class_name="author-country"),
            spacing="1",
        ),
        rx.hstack(
            rx.text("tags:"),
            rx.foreach(b.tags, lambda t: rx.badge(t.label, class_name="tag-badge")),
            spacing="1",
        ),
        class_name="book-row",
    )


def index() -> rx.Component:
    return rx.container(
        rx.heading("db relationships", size="5"),
        rx.hstack(
            rx.button("seed", on_click=State.seed, id="btn-seed"),
            rx.button("load sync", on_click=State.load_books_sync, id="btn-sync"),
            rx.button("load async", on_click=State.load_authors_async, id="btn-async"),
            rx.button("load no-eager", on_click=State.load_no_eager, id="btn-noeager"),
            rx.button("bg load", on_click=State.bg_load, id="btn-bg"),
            rx.button("chain", on_click=State.chain_all, id="btn-chain"),
            wrap="wrap",
        ),
        rx.hstack(
            rx.button("dyn", on_click=State.do_dyn, id="btn-dyn"),
            rx.button("custom", on_click=State.do_custom, id="btn-custom"),
            rx.button("fields", on_click=State.do_fields, id="btn-fields"),
            wrap="wrap",
        ),
        rx.divider(),
        rx.text("count: ", rx.text.strong(State.seed_count.to_string(), id="count")),
        rx.heading("books (foreach + relationship field access)", size="3"),
        rx.box(rx.foreach(State.books, book_row), id="books"),
        rx.heading("single book ObjectVar", size="3"),
        rx.cond(
            State.single_book,
            rx.text(
                State.single_book.title,
                " -> ",
                State.single_book.author.name,
                id="single-book",
            ),
            rx.text("none", id="single-book"),
        ),
        rx.heading("authors (nested books)", size="3"),
        rx.box(
            rx.foreach(
                State.authors,
                lambda a: rx.box(
                    rx.text(a.name, " [", a.country, "]", weight="bold"),
                    rx.foreach(a.books, lambda b: rx.text("  - ", b.title)),
                    class_name="author-row",
                ),
            ),
            id="authors",
        ),
        rx.divider(),
        rx.text("modules at import: ", State.modules_at_import.join(","), id="mods-import"),
        rx.text("modules now: ", State.modules_now.join(","), id="mods-now"),
        rx.text("dyn: ", State.dyn_serialized, id="dyn-out"),
        rx.text("custom: ", State.custom_serialized, id="custom-out"),
        rx.text("fields: ", State.fields_dump, id="fields-out"),
        rx.text("bg: ", State.bg_result, id="bg-out"),
        rx.text("log: ", State.log.join(" | "), id="log-out"),
        padding="1em",
    )


app = rx.App()
app.add_page(index, route="/", on_load=State.on_load)
