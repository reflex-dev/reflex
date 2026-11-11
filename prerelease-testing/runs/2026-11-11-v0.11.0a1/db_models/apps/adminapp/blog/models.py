"""New-style (0.11 docs) models: MappedAsDataclass + DeclarativeBase, same tables."""

import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, ForeignKey, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column, relationship

import reflex as rx


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    writer = "writer"
    editor = "editor"


class Base(MappedAsDataclass, DeclarativeBase):
    """Base class for the app's tables."""


rx.ModelRegistry.register(Base)


posttaglink = Table(
    "posttaglink",
    Base.metadata,
    Column("post_id", ForeignKey("post.id"), primary_key=True),
    Column("tag_id", ForeignKey("tag.id"), primary_key=True),
)


class Author(Base):
    __tablename__ = "author"

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, index=True)
    email: Mapped[str | None] = mapped_column(default=None)
    role: Mapped[Role] = mapped_column(default=Role.writer)
    joined_at: Mapped[datetime] = mapped_column(default_factory=utcnow)
    profile: Mapped[dict | None] = mapped_column(JSON, default_factory=dict)
    bio: Mapped[str | None] = mapped_column(default=None)

    posts: Mapped[list["Post"]] = relationship(back_populates="author", default_factory=list, repr=False)


class Tag(Base):
    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)

    posts: Mapped[list["Post"]] = relationship(
        secondary=posttaglink, back_populates="tags", default_factory=list, repr=False
    )


class Post(Base):
    __tablename__ = "post"

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    title: Mapped[str] = mapped_column(index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("author.id"))
    body: Mapped[str] = mapped_column(default="")
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)
    views: Mapped[int] = mapped_column(default=0)

    author: Mapped[Author] = relationship(back_populates="posts", init=False, repr=False)
    tags: Mapped[list[Tag]] = relationship(
        secondary=posttaglink, back_populates="posts", default_factory=list, repr=False
    )
