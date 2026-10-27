# Tables

Tables are database objects that contain all the data in a database.

In tables, data is logically organized in a row-and-column format similar to a
spreadsheet. Each row represents a unique record, and each column represents a
field in the record.

## Creating a Table

Tables are [SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)
models. Define one base class for the app and make each table a subclass of it.

```python
import reflex as rx
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column


class Base(MappedAsDataclass, DeclarativeBase):
    """Base class for the app's tables."""


rx.ModelRegistry.register(Base)


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    username: Mapped[str]
    email: Mapped[str]
```

Each `Mapped[...]` annotation becomes a column whose SQL type is derived from the
Python type. `MappedAsDataclass` makes the model a dataclass, so `User(username="test", email="test@example.com")`
constructs a row and Reflex can store `User` instances in state and render their
fields in components. `rx.ModelRegistry.register(Base)` lets the `reflex db`
[migration commands](/docs/database/overview/#migrations) find the tables.

Dataclass fields without a default must come before fields with one, so declare
required columns first and optional columns, with `default=None` or
`default_factory`, after them.

### Primary Key

Every table needs a primary key. Declare it with `primary_key=True`; `init=False`
excludes it from the constructor so the database assigns it on insert.

```python
class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    ...
```

## Advanced Column Types

### Nullable and Optional Columns

A column annotated with `| None` is nullable. Give it `default=None` so it can
be left out when constructing the row.

```python
from datetime import datetime


class Post(Base):
    __tablename__ = "post"

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    title: Mapped[str]
    body: Mapped[str]
    published_at: Mapped[datetime | None] = mapped_column(default=None)
```

### Explicit column types

SQLAlchemy maps basic Python types to column types, but for more advanced use
cases, pass the column type to `mapped_column` directly. For example, we can add
a last updated timestamp to the post example as a `DateTime` with timezone that
the database fills in.

```python
import datetime

import sqlalchemy


class Post(Base):
    __tablename__ = "post"

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    ...
    update_ts: Mapped[datetime.datetime] = mapped_column(
        sqlalchemy.DateTime(timezone=True),
        init=False,
        server_default=sqlalchemy.func.now(),
    )
```

Reflex serializes `datetime` values to ISO strings for the frontend. To change
how a model is sent to the frontend, register a serializer for it. This one
strips the microseconds from `update_ts`:

```python
import dataclasses

import reflex as rx


@rx.serializer
def serialize_post(post: Post) -> dict:
    data = dataclasses.asdict(post)
    data["update_ts"] = post.update_ts.replace(microsecond=0).isoformat()
    return data
```

## Existing `rx.Model` apps

`rx.Model` is deprecated as of Reflex 0.9.2 and is scheduled for removal in
1.0.0. See [Migrating existing apps](/docs/database/overview/#migrating-existing-apps)
for the equivalent SQLAlchemy declarations. The note below applies to apps that
still use `rx.Model` or SQLModel directly.

### Datetimes and SQLModel upgrades

From SQLModel 0.0.45, a plain `datetime` field uses `UTCDateTime`:
database writes require timezone-aware values, and reads return UTC-aware values,
including on SQLite. Migrations generated with these versions reference
`sqlmodel.sql.sqltypes.UTCDateTime()` and require SQLModel 0.0.45 or later when
they run. Keep the SQLModel version used to generate migrations in your deployment
dependencies; for example, `sqlmodel>=0.0.45` if a migration uses `UTCDateTime`.

Reflex does not cap the SQLModel version, so a fresh install, or an upgrade that
refreshes every dependency such as `uv pip install -U`, can move an app from
SQLModel 0.0.44 to 0.0.45 or later. `pip install -U` and `uv pip install` without
`-U` leave an installed SQLModel in place. After the move, naive `datetime` values
are rejected when written, and values read back are timezone-aware, so comparing
them with `datetime.now()` raises
`TypeError: can't compare offset-naive and offset-aware datetimes`. To keep naive
datetimes, declare the column explicitly as shown below, or pin `sqlmodel<0.0.45`
while no migration references `UTCDateTime`.

For existing apps that store naive datetimes, declare the SQLAlchemy type
explicitly to preserve that behavior across SQLModel versions:

```python
from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field


class Post(rx.Model, table=True):
    created_at: datetime = Field(
        default_factory=datetime.now,
        sa_type=DateTime(timezone=False),
    )
```

On SQLModel 0.0.45 or later, Pydantic's `NaiveDatetime` annotation also selects
naive storage. For UTC storage, use aware producers such as
`datetime.now(timezone.utc)`, and update comparisons, query parameters, and
database defaults to use aware values. Changing the Python field type does not
convert existing database values: determine the timezone of stored data and
apply a database-specific migration before adopting UTC storage. Follow
[SQLModel's datetime upgrade guide](https://sqlmodel.tiangolo.com/advanced/datetime/#upgrade-existing-applications)
for the PostgreSQL, SQLite, and MySQL migration details.
