---
meta_description: Build Reflex dashboards and internal tools with MySQL, PostgreSQL, SQL Server, or SQLite using SQLAlchemy models, database sessions, and migrations.
---

# Database Overview

Connect a Reflex Python app to **MySQL, PostgreSQL, SQL Server, or SQLite** to build database-driven dashboards, admin panels, and internal tools. Define tables as Python classes with [SQLAlchemy](https://docs.sqlalchemy.org/en/20/), query them in the app's Python backend, and load the results into state to render them, without creating a separate API service just for the UI.

## Key takeaways

- Define tables as SQLAlchemy models on a shared dataclass-mapped base. Reflex serializes those models, so they can be stored in state and rendered directly.
- Create one engine and one session factory for the app, and open a short-lived session inside each event handler that reads or writes the database.
- Configure the database URL and install the driver for your chosen database. Check dialect-specific types, queries, and migrations when switching databases.
- Register the model base with Reflex to manage schema changes with the `reflex db` migration commands.
- Use ordinary Python clients or REST APIs for external data sources such as Airtable, Databricks, and Snowflake.

## Supported databases

| Database | Connection approach | Typical use |
| --- | --- | --- |
| MySQL | SQLAlchemy dialect and a MySQL DBAPI driver | Apps connected to an existing MySQL database |
| PostgreSQL | SQLAlchemy dialect and a PostgreSQL DBAPI driver | Production apps with a shared relational database |
| SQL Server | SQLAlchemy MSSQL dialect and a compatible driver | Apps connected to Microsoft SQL Server |
| SQLite | Local database file | Local development and small applications |

```md alert info
# Using NoSQL Databases

If you are using a NoSQL database (e.g. MongoDB), you can work with it in Reflex by installing the appropriate Python client library. In this case, Reflex will not provide any ORM features.
```

## Installation

Install SQLAlchemy together with the DBAPI driver for your database. The `db`
extra installs SQLAlchemy and [Alembic](https://alembic.sqlalchemy.org/en/latest/),
which the `reflex db` migration commands use:

```bash
pip install "reflex[db]"
```

SQLite needs no extra driver. For other databases, install the driver named in
the [SQLAlchemy dialect docs](https://docs.sqlalchemy.org/en/20/dialects/), for
example `psycopg[binary]` for PostgreSQL.

## Connecting

Set the database URL in `rxconfig.py`. The `reflex db` migration commands read
it from there, and the app can read it back through `rx.config.get_config()`
so the URL lives in one place.

```python
import reflex as rx

config = rx.Config(
    app_name="my_app",
    db_url="sqlite:///reflex.db",
)
```

For more examples of database URLs that can be used, see the [SQLAlchemy
docs](https://docs.sqlalchemy.org/en/20/core/engines.html#backend-specific-urls).

Create the engine and a session factory once, in a module the rest of the app
imports. `expire_on_commit=False` keeps the attributes of committed objects
readable after the session closes, which is what lets them be stored in state.

```python
# my_app/db.py
import reflex as rx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(rx.config.get_config().db_url)
Session = sessionmaker(engine, expire_on_commit=False)
```

## Tables

Define a base class with `MappedAsDataclass` and `DeclarativeBase`, and make
each table a subclass of it. The dataclass mapping gives every model a
keyword-argument constructor and lets Reflex serialize instances into state
without extra code.

```python
# my_app/models.py
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

`rx.ModelRegistry.register(Base)` tells the `reflex db` commands which tables
to manage. See [Tables](/docs/database/tables/) for column types and
[Relationships](/docs/database/relationships/) for foreign keys.

## Migrations

Reflex leverages [alembic](https://alembic.sqlalchemy.org/en/latest/)
to manage database schema changes.

Before the database feature can be used in a new app you must call `reflex db init`
to initialize alembic and create a migration script with the current schema.

After making changes to the schema, use
`reflex db makemigrations --message 'something changed'`
to generate a script in the `alembic/versions` directory that will update the
database schema. It is recommended that generated scripts be inspected before applying them.

Bear in mind that your newest models will not be detected by the `reflex db makemigrations`
command unless imported and used somewhere within the application.

The `reflex db migrate` command is used to apply migration scripts to bring the
database up to date. During app startup, if Reflex detects that the current
database schema is not up to date, a warning will be displayed on the console.

For a local experiment, `Base.metadata.create_all(engine)` creates any missing
tables without migrations.

## Queries

Open a session from the factory inside an event handler. The `with` block
closes the session when it ends, and changes that were not committed are rolled
back.

```python
import reflex as rx
from sqlalchemy import select

from .db import Session
from .models import User


class UserState(rx.State):
    users: list[User] = []

    @rx.event
    def add_user(self):
        with Session() as session:
            session.add(User(username="test", email="admin@reflex.dev"))
            session.commit()

    @rx.event
    def load_users(self):
        with Session() as session:
            self.users = session.scalars(select(User)).all()
```

Because `User` is a dataclass-mapped model, `self.users` serializes to the
frontend and each row renders with `rx.foreach(UserState.users, ...)`. See
[Queries](/docs/database/queries/) for updates, deletes, raw SQL, and async
sessions.

```md video https://youtube.com/embed/ITOZkzjtjUA?start=6835&end=8225
# Video: Tutorial of Database Model with Forms, Model Field Changes and Migrations, and adding a DateTime Field
```

## Migrating existing apps

`rx.Model` and `rx.session()` are deprecated as of Reflex 0.9.2 and will be
removed in 1.0. Existing apps move to the pattern above with these
replacements:

| Deprecated | Replacement |
| :--- | :--- |
| `class User(rx.Model, table=True)` | `class User(Base)` with `__tablename__` and `Mapped[...]` columns |
| implicit `id` primary key | `id: Mapped[int] = mapped_column(init=False, primary_key=True)` |
| `with rx.session() as session` | `with Session() as session` from your `sessionmaker` |
| `session.exec(select(User)).all()` | `session.scalars(select(User)).all()` |
| `session.exec(select(User)).first()` | `session.scalar(select(User))` |
| `async with rx.asession() as session` | `async with AsyncSession() as session` from your `async_sessionmaker` |
| `sqlmodel.Field(foreign_key="user.id")` | `mapped_column(ForeignKey("user.id"))` |
| `sqlmodel.Relationship(back_populates=...)` | `relationship(back_populates=..., repr=False)` |

Columns, data, and migration history are unchanged, since both map to the same
tables. Existing apps that store naive datetimes should read
[Datetimes and SQLModel upgrades](/docs/database/tables/#datetimes-and-sqlmodel-upgrades)
before upgrading SQLModel.

## Beyond the ORM

For services such as Airtable, Databricks, or Snowflake, use their Python libraries or REST APIs in your backend. These connections are separate from the relational ORM described above. See the [AI and API integrations overview](/docs/ai/integrations/overview/) for available integrations and custom connection options.

To replace the in-memory data in the [dashboard tutorial](/docs/getting-started/dashboard-tutorial/), query your database into state and persist new records in the form's event handler. Refresh the state after a write so the table and chart display the latest results.

<!-- faqs-start -->
<!-- faqs-visible -->

## FAQ

### Which databases does Reflex support?

Reflex apps use SQLAlchemy to connect to MySQL, PostgreSQL, SQL Server, and SQLite. Define tables as Python classes, configure the database URL, and install the appropriate DBAPI driver. Queries run in the Python backend through database sessions.

### Can a Reflex app connect to MySQL, SQL Server, or SQLite instead of PostgreSQL?

Yes. Configure the database URL and driver for your chosen database. Many model and query patterns are portable, but review database-specific types, SQL features, constraints, and migrations when switching engines. Existing data must also be migrated.

### Can Reflex connect to data sources without a prebuilt connector, like Airtable or Databricks?

Yes. A Reflex app can use Python libraries or REST APIs to access Airtable, Databricks, Snowflake, and other services. Keep credentials in the backend, query the service in your application logic, and assign results to state for display.

<!-- faqs-end -->
