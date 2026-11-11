"""tables.md custom serializer (dataclasses.asdict) applied to a model that has relationships (relationships.md)."""
import asyncio
import dataclasses
import sys

import reflex

assert sys.argv[1] in reflex.__file__, reflex.__file__
import reflex as rx
from reflex_base.utils.serializers import serialize
from sqlalchemy import ForeignKey, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column, relationship, selectinload


class Base(MappedAsDataclass, DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    username: Mapped[str]
    posts: Mapped[list["Post"]] = relationship(back_populates="user", default_factory=list, repr=False)


class Post(Base):
    __tablename__ = "post"
    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    title: Mapped[str]
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    user: Mapped[User] = relationship(back_populates="posts", init=False, repr=False)


@rx.serializer
def serialize_post(post: Post) -> dict:
    data = dataclasses.asdict(post)
    data["title"] = data["title"].upper()
    return data


async def main():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        s.add(User(username="alice"))
        await s.flush()
        s.add(Post(title="p1", user_id=1))
        await s.commit()
    for label, opts in [("no rel loaded", []), ("Post.user loaded", [selectinload(Post.user)]),
                        ("Post.user.posts loaded (cycle)", [selectinload(Post.user).selectinload(User.posts)])]:
        async with Session() as s:
            p = await s.scalar(select(Post).options(*opts))
        try:
            print(label, "->", serialize(p))
        except BaseException as e:
            print(label, "-> ERR", type(e).__name__, str(e)[:200])
    await engine.dispose()


asyncio.run(main())
