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
