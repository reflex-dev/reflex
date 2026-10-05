"""Compare relationship serialization payloads across reflex versions (no server)."""
import json, sys, os
import reflex, reflex as rx
assert "/envs/" in reflex.__file__, reflex.__file__
import sqlmodel
from sqlmodel import Field, Relationship
from sqlalchemy.orm import selectinload
from typing import Optional

DB = sys.argv[1]
os.environ.setdefault("REFLEX_TELEMETRY_ENABLED", "false")

class BookTagLink(rx.Model, table=True):
    book_id: int | None = Field(default=None, foreign_key="book.id")
    tag_id: int | None = Field(default=None, foreign_key="tag.id")

class Author(rx.Model, table=True):
    name: str
    country: str = "US"
    books: list["Book"] = Relationship(back_populates="author")

class Tag(rx.Model, table=True):
    label: str
    books: list["Book"] = Relationship(back_populates="tags", link_model=BookTagLink)

class Book(rx.Model, table=True):
    title: str
    year: int = 2000
    author_id: int | None = Field(default=None, foreign_key="author.id")
    author: Optional[Author] = Relationship(back_populates="books")
    tags: list[Tag] = Relationship(back_populates="books", link_model=BookTagLink)

from reflex_base.utils import serializers as S
engine = sqlmodel.create_engine(f"sqlite:///{DB}")
with sqlmodel.Session(engine) as s:
    books = s.exec(sqlmodel.select(Book).options(selectinload(Book.author), selectinload(Book.tags)).order_by(Book.id)).all()
    out = [S.serialize(b) for b in books]
print("VERSION:", reflex.constants.Reflex.VERSION)
print("PAYLOAD:", json.dumps(out, sort_keys=True, default=str))
# ObjectVar field access type resolution through the relationship
from reflex_base.utils import types as T
print("attr_type(Book,'author'):", T.get_attribute_access_type(Book, "author"))
print("attr_type(Book,'tags'):", T.get_attribute_access_type(Book, "tags"))
print("attr_type(Author,'books'):", T.get_attribute_access_type(Author, "books"))
