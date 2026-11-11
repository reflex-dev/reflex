import os
import dataclasses

from sqlalchemy import Column, ForeignKey, Table, func
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, column_property, mapped_column, relationship, synonym

import reflex as rx


class Base(MappedAsDataclass, DeclarativeBase):
    """Base class for the app's tables."""


rx.ModelRegistry.register(Base)

post_tag = Table(
    "post_tag", Base.metadata,
    Column("post_id", ForeignKey("post.id"), primary_key=True),
    Column("tag_id", ForeignKey("tag.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    username: Mapped[str] = mapped_column()
    email: Mapped[str]
    nick: Mapped[str] = synonym("username", init=False)
    name_len: Mapped[int] = column_property(func.length(username), init=False)

    posts: Mapped[list["Post"]] = relationship(back_populates="user", default_factory=list, repr=False)
    flags: Mapped[list["Flag"]] = relationship(back_populates="user", default_factory=list, repr=False)

    @hybrid_property
    def upper_name(self) -> str:
        return self.username.upper()


class Tag(Base):
    __tablename__ = "tag"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    posts: Mapped[list["Post"]] = relationship(secondary=post_tag, back_populates="tags", default_factory=list, repr=False)


class Post(Base):
    __tablename__ = "post"

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    title: Mapped[str]
    body: Mapped[str]
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))

    user: Mapped["User"] = relationship(back_populates="posts", init=False, repr=False)
    flags: Mapped[list["Flag"]] = relationship(back_populates="post", default_factory=list, repr=False)
    tags: Mapped[list[Tag]] = relationship(secondary=post_tag, back_populates="posts", default_factory=list, repr=False)


class Flag(Base):
    __tablename__ = "flag"

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("post.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    message: Mapped[str]

    post: Mapped[Post] = relationship(back_populates="flags", init=False, repr=False)
    user: Mapped[User] = relationship(back_populates="flags", init=False, repr=False)


if os.environ.get("LEGACY_SER") == "1":
    # A user's own serializer (shape of the tables.md example, made relationship-safe)
    @rx.serializer
    def serialize_tag(tag: Tag) -> dict:
        return {"id": tag.id, "name": "LEGACY:" + tag.name}

