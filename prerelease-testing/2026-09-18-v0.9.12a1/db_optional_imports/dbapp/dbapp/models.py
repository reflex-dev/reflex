"""Models: Author 1-N Book, Book N-N Tag via link table."""

from typing import Optional

import reflex as rx
import sqlmodel
from sqlmodel import Field, Relationship


class BookTagLink(rx.Model, table=True):
    # rx.Model already supplies the `id` primary key, so the FKs are plain columns.
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
