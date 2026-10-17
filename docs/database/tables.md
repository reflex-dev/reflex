# Tables

Tables are database objects that contain all the data in a database.

In tables, data is logically organized in a row-and-column format similar to a
spreadsheet. Each row represents a unique record, and each column represents a
field in the record.

## Creating a Table

To create a table, make a class that inherits from `rx.Model`.

The following example shows how to create a table called `User`.

```python
class User(rx.Model, table=True):
    username: str
    email: str
```

The `table=True` argument tells Reflex to create a table in the database for
this class.

### Primary Key

By default, Reflex will create a primary key column called `id` for each table.

However, if an `rx.Model` defines a different field with `primary_key=True`, then the
default `id` field will not be created. A table may also redefine `id` as needed.

It is not currently possible to create a table without a primary key.

## Advanced Column Types

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

### Explicit column types

SQLModel automatically maps basic python types to SQLAlchemy column types, but
for more advanced use cases, it is possible to define the column type using
`sqlalchemy` directly. For example, we can add a last updated timestamp to the
post example as a proper `DateTime` field with timezone.

```python
import datetime

import sqlmodel
import sqlalchemy


class Post(rx.Model, table=True):
    ...
    update_ts: datetime.datetime = sqlmodel.Field(
        default=None,
        sa_column=sqlalchemy.Column(
            "update_ts",
            sqlalchemy.DateTime(timezone=True),
            server_default=sqlalchemy.func.now(),
        ),
    )
```

To make the `Post` model more usable on the frontend, a `dict` method may be provided
that converts any fields to a JSON serializable value. In this case, the dict method is
overriding the default `datetime` serializer to strip off the microsecond part.

```python
class Post(rx.Model, table=True):
    ...

    def dict(self, *args, **kwargs) -> dict:
        d = super().dict(*args, **kwargs)
        d["update_ts"] = self.update_ts.replace(microsecond=0).isoformat()
        return d
```
