"""Python-level probes of the DeclarativeBase serializer and var typing (#7756, #7648)."""
import asyncio
import json
import sys

import reflex

assert sys.argv[1] in reflex.__file__, reflex.__file__
import reflex as rx
from reflex_base.utils.serializers import serialize
from sqlalchemy import ForeignKey, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import (DeclarativeBase, Mapped, MappedAsDataclass, column_property, deferred,
                            mapped_column, relationship, selectinload, synonym)


class Base(MappedAsDataclass, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    username: Mapped[str] = mapped_column()
    secret: Mapped[str] = mapped_column(deferred=True, default="s3cret")
    nick: Mapped[str] = synonym("username", init=False)
    name_len: Mapped[int] = column_property(func.length(username), init=False)
    posts: Mapped[list["Post"]] = relationship(back_populates="user", default_factory=list, repr=False)

    @property
    def display(self) -> str:
        return "@" + self.username

    @hybrid_property
    def upper_name(self) -> str:
        return self.username.upper()


class Post(Base):
    __tablename__ = "post"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    title: Mapped[str]
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    user: Mapped[User] = relationship(back_populates="posts", init=False, repr=False)


class S(rx.State):
    user: User | None = None
    posts: list[Post] = []


def show(label, fn):
    try:
        print(label, "->", fn())
    except Exception as e:
        print(label, "-> ERR", type(e).__name__, str(e)[:300])


show("S.user.nick type", lambda: (S.user.nick._var_type, type(S.user.nick).__name__))
show("S.user.nick.upper()", lambda: str(S.user.nick.upper()))
show("S.user.display (@property)", lambda: str(S.user.display))
show("S.user.upper_name (hybrid)", lambda: (str(S.user.upper_name), S.user.upper_name._var_type))
show("S.user.name_len (column_property)", lambda: (str(S.user.name_len), S.user.name_len._var_type))
show("S.user.secret (deferred)", lambda: (str(S.user.secret), S.user.secret._var_type))
show("S.user.posts type", lambda: S.user.posts._var_type)
show("S.posts[0].user.username", lambda: str(S.posts[0].user.username))


async def main():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        u = User(username="alice")
        s.add(u)
        s.add(Post(title="p1", user_id=1))
        print("transient/pending:", json.dumps(serialize(u), default=str))
        await s.commit()
        print("after commit (expire_on_commit=False):", serialize(u))
    async with Session() as s:
        u = await s.scalar(select(User))
        print("loaded, no rels:", serialize(u))
        u = await s.scalar(select(User).options(selectinload(User.posts)).execution_options(populate_existing=True))
        print("loaded, posts:", serialize(u))
        p = await s.scalar(select(Post).options(selectinload(Post.user).selectinload(User.posts)))
        print("post w/ user.posts (cycle):", serialize(p))
    S2 = async_sessionmaker(engine)  # default expire_on_commit=True
    async with S2() as s:
        u = await s.scalar(select(User))
        u.username = "alice2"
        await s.commit()
        print("after commit, expire_on_commit=True:", serialize(u))
    print("after session closed (expired):", serialize(u))
    await engine.dispose()


asyncio.run(main())
