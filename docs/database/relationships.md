# Relationships

Foreign key relationships are used to link two tables together. For example,
the `Post` model may have a field, `user_id`, with a foreign key of `user.id`,
referencing a `User` model. This would allow us to automatically query the `Post` objects
associated with a user, or find the `User` object associated with a `Post`.

To establish bidirectional relationships a model must correctly set the
`back_populates` keyword argument on the `relationship()` to the relationship
attribute in the _other_ model.

## Foreign Key Relationships

To create a relationship, first add a column that references the primary key of
the related table with `ForeignKey`, then add a `relationship()` attribute which
can be used to access the related objects.

```python
import reflex as rx
from sqlalchemy import ForeignKey
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
    relationship,
)


class Base(MappedAsDataclass, DeclarativeBase):
    """Base class for the app's tables."""


rx.ModelRegistry.register(Base)


class Post(Base):
    __tablename__ = "post"

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    title: Mapped[str]
    body: Mapped[str]
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))

    user: Mapped["User"] = relationship(back_populates="posts", init=False, repr=False)
    flags: Mapped[list["Flag"]] = relationship(
        back_populates="post", default_factory=list, repr=False
    )


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    username: Mapped[str]
    email: Mapped[str]

    posts: Mapped[list[Post]] = relationship(
        back_populates="user", default_factory=list, repr=False
    )
    flags: Mapped[list["Flag"]] = relationship(
        back_populates="user", default_factory=list, repr=False
    )


class Flag(Base):
    __tablename__ = "flag"

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("post.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    message: Mapped[str]

    post: Mapped[Post] = relationship(back_populates="flags", init=False, repr=False)
    user: Mapped[User] = relationship(back_populates="flags", init=False, repr=False)
```

Relationships are declared with `repr=False` because the dataclass `repr`
would otherwise follow every link, and with `init=False` or a
`default_factory` so the constructor takes the foreign key column instead.

See the [SQLAlchemy Relationship Docs](https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html)
for more details.

## Serializing Linked Objects

Reflex serializes a dataclass-mapped model field by field, and reading a
relationship that was not loaded raises an error, because an async session never
loads one implicitly on attribute access. Register a serializer for the base class that sends
only the attributes a query loaded, so linked objects render when they were
eager-loaded and are simply absent when they were not:

```python
from typing import Any

import sqlalchemy


@rx.serializer
def serialize_model(model: Base) -> dict[str, Any]:
    """Send a model's loaded columns and relationships to the frontend."""
    state = sqlalchemy.inspect(model)
    return {
        attr.key: attr.value for attr in state.attrs if attr.key not in state.unloaded
    }
```

## Querying Relationships

The examples below open sessions with the async `Session` factory from the
[database overview](/docs/database/overview/#connecting).

### Inserting Linked Objects

The following example assumes that the flagging user is stored in the state as a
`User` instance and that the post `id` is provided in the data submitted in the
form.

```python
class FlagPostForm(rx.State):
    user: User

    @rx.event
    async def flag_post(self, form_data: dict[str, Any]):
        async with Session() as session:
            flag = Flag(
                message=form_data.pop("message"),
                post_id=int(form_data.pop("post_id")),
                user_id=self.user.id,
            )
            session.add(flag)
            await session.commit()
```

### How are Relationships Dereferenced?

By default, the relationship attributes are in **lazy loading** or `"select"`
mode, which generates a query _on access_ to the relationship attribute. An
async session cannot run that query implicitly, so reading a relationship that
was not loaded raises an error instead. Load the relationships a handler or the
UI reads up front, with one of these eager loading mechanisms, set on the
relationship object or when performing the query.

- "joined" or `joinedload` - generates a single query to load all related objects
  at once.
- "subquery" or `subqueryload` - generates a single query to load all related
  objects at once, but uses a subquery to do the join, instead of a join in the
  main query.
- "selectin" or `selectinload` - emits a second (or more) SELECT statement which
  assembles the primary key identifiers of the parent objects into an IN clause,
  so that all members of related collections / scalar references are loaded at
  once by primary key

There are also non-loading mechanisms, "raise" and "noload" which are used to
specifically avoid loading a relationship. To load a relationship on an object
you already have, await `session.refresh(obj, ["relationship_name"])`.

Each loading method comes with tradeoffs and some are better suited for different
data access patterns.
See [SQLAlchemy: Relationship Loading Techniques](https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html)
for more detail.

### Querying Linked Objects

To query the `Post` table and include all `User` and `Flag` objects up front,
the `.options` interface will be used to specify `selectinload` for the required
relationships. Using this method, the linked objects will be available for
rendering in frontend code without additional steps.

```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload


class PostState(rx.State):
    posts: list[Post] = []

    @rx.event
    async def load_posts(self):
        async with Session() as session:
            result = await session.scalars(
                select(Post)
                .options(
                    selectinload(Post.user),
                    selectinload(Post.flags).selectinload(Flag.user),
                )
                .limit(15)
            )
            self.posts = result.all()
```

The loading methods create new query objects and thus may be chained if the
relationship itself has other relationships that need to be loaded. In this
example, since `Flag` references `User`, the `Flag.user` relationship must be
chain loaded from the `Post.flags` relationship.

### Specifying the Loading Mechanism on the Relationship

Alternatively, the loading mechanism can be specified on the relationship by
passing `lazy=method` to `relationship()`, which will use the given loading
mechanism in all queries by default.

```python
class Post(Base):
    __tablename__ = "post"
    ...
    user: Mapped["User"] = relationship(
        back_populates="posts",
        lazy="selectin",
        init=False,
        repr=False,
    )
    flags: Mapped[list["Flag"]] = relationship(
        back_populates="post",
        lazy="selectin",
        default_factory=list,
        repr=False,
    )
```

### Querying Related Rows on Demand

For master-detail interfaces — a table of parent rows where selecting a row
reveals its related rows — it is not necessary to eager load every
relationship up front. Store the selected id in state and query only the
related rows for that selection, filtering on the foreign key.

```python
import reflex as rx
from sqlalchemy import select


class PostFlagsState(rx.State):
    posts: list[Post] = []
    selected_post_id: int | None = None
    selected_flags: list[Flag] = []

    @rx.event
    async def load_posts(self):
        async with Session() as session:
            self.posts = (await session.scalars(select(Post).limit(15))).all()

    @rx.event
    async def select_post(self, post_id: int):
        self.selected_post_id = post_id
        async with Session() as session:
            result = await session.scalars(select(Flag).where(Flag.post_id == post_id))
            self.selected_flags = result.all()
```

This runs a single indexed query per selection and avoids holding every child
row in state — the `index=True` on `Flag.post_id` keeps the foreign-key lookup
off a full table scan (adding the index to an existing table requires a
migration). Avoid the inverse pattern of querying children in a Python loop
over parents (the "N+1" pattern) — when the children of many parents are
needed at once, use one query with `.in_()` on the foreign key, or one of the
eager loading options above.

```python
post_ids = [post.id for post in self.posts]
async with Session() as session:
    result = await session.scalars(select(Flag).where(Flag.post_id.in_(post_ids)))
    flags = result.all()
```
