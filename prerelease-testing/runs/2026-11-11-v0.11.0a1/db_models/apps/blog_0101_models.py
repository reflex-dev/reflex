"""Old-style (reflex 0.10.1) models: rx.Model / sqlmodel."""

import enum
from datetime import datetime, timezone

import sqlalchemy as sa
import sqlmodel

import reflex as rx


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    writer = "writer"
    editor = "editor"


class PostTagLink(sqlmodel.SQLModel, table=True):
    post_id: int | None = sqlmodel.Field(default=None, foreign_key="post.id", primary_key=True)
    tag_id: int | None = sqlmodel.Field(default=None, foreign_key="tag.id", primary_key=True)


class Author(rx.Model, table=True):
    name: str = sqlmodel.Field(unique=True, index=True)
    email: str | None = None
    role: Role = Role.writer
    joined_at: datetime = sqlmodel.Field(default_factory=utcnow)
    profile: dict = sqlmodel.Field(default_factory=dict, sa_column=sa.Column(sa.JSON))
    bio: str | None = None
    posts: list["Post"] = sqlmodel.Relationship(back_populates="author")


class Tag(rx.Model, table=True):
    name: str = sqlmodel.Field(unique=True)
    posts: list["Post"] = sqlmodel.Relationship(back_populates="tags", link_model=PostTagLink)


class Post(rx.Model, table=True):
    title: str = sqlmodel.Field(index=True)
    body: str = ""
    author_id: int = sqlmodel.Field(foreign_key="author.id")
    created_at: datetime = sqlmodel.Field(default_factory=utcnow)
    views: int = 0
    author: Author | None = sqlmodel.Relationship(back_populates="posts")
    tags: list[Tag] = sqlmodel.Relationship(back_populates="posts", link_model=PostTagLink)
