---
meta_description: Connect Reflex apps to MySQL, PostgreSQL, SQL Server, and SQLite with Python models, database sessions, and migrations. Build database-driven dashboards and internal tools.
---

# Database Overview

Connect a Reflex Python app to **MySQL, PostgreSQL, SQL Server, or SQLite** to build database-driven dashboards, admin panels, and internal tools. Define models as Python classes and query them in the app's Python backend without creating a separate API service just for the UI.

## Key takeaways

- Install the optional database dependencies with the `db` extra.
- Define tables with `rx.Model`, query them with `rx.session()`, and manage schema changes with migrations.
- Configure the database URL and install the driver for your chosen database. Check dialect-specific types, queries, and migrations when switching databases.
- Load query results into state to display them in the UI. External database changes require another query, polling, or an event to refresh the app.
- Use ordinary Python clients or REST APIs for external data sources such as Airtable, Databricks, and Snowflake.

## Supported databases

| Database | Connection approach | Typical use |
| --- | --- | --- |
| MySQL | SQLAlchemy dialect and a MySQL DBAPI driver | Apps connected to an existing MySQL database |
| PostgreSQL | SQLAlchemy dialect and a PostgreSQL DBAPI driver | Production apps with a shared relational database |
| SQL Server | SQLAlchemy MSSQL dialect and a compatible driver | Apps connected to Microsoft SQL Server |
| SQLite | Local database file | Local development and small applications |

Reflex uses [sqlmodel](https://sqlmodel.tiangolo.com) to provide a built-in ORM wrapping SQLAlchemy.

```md alert warning
# ORM compatibility

`rx.Model` is deprecated as of Reflex 0.9.2 and is scheduled for removal in 1.0.0. The examples below document the existing Reflex ORM interface. For new applications, use SQLModel or SQLAlchemy directly with your own engine and sessions; the same database connection and Python state patterns still apply.
```

The examples on this page refer specifically to how Reflex uses various tools to
expose an integrated database interface. Only basic use cases will be covered
below, but you can refer to the
[sqlmodel tutorial](https://sqlmodel.tiangolo.com/tutorial/select/)
for more examples and information, just replace `SQLModel` with `rx.Model` and
`Session(engine)` with `rx.session()`

For advanced use cases, please see the
[SQLAlchemy docs](https://docs.sqlalchemy.org/en/14/orm/quickstart.html) (v1.4).

```md alert info
# Using NoSQL Databases

If you are using a NoSQL database (e.g. MongoDB), you can work with it in Reflex by installing the appropriate Python client library. In this case, Reflex will not provide any ORM features.
```

## Installation

The ORM dependencies (SQLModel and Alembic) are an optional extra.
Install them with the `db` extra:

```bash
pip install "reflex[db]"
```

## Connecting

Reflex provides a built-in SQLite database for storing and retrieving data.

You can connect to your own SQL compatible database by modifying the
`rxconfig.py` file with your database url.

```python
import reflex as rx

config = rx.Config(
    app_name="my_app",
    db_url="sqlite:///reflex.db",
)
```

For more examples of database URLs that can be used, see the [SQLAlchemy
docs](https://docs.sqlalchemy.org/en/14/core/engines.html#backend-specific-urls).
Be sure to install the appropriate DBAPI driver for the database you intend to
use.

## Tables

To create a table make a class that inherits from `rx.Model` and specify
that it is a table.

```python
import reflex as rx


class User(rx.Model, table=True):
    username: str
    email: str
```

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

## Queries

To query the database you can create a `rx.session()`
which handles opening and closing the database connection.

You can use normal SQLAlchemy queries to query the database.

```python
with rx.session() as session:
    session.add(User(username="test", email="admin@reflex.dev"))
    session.commit()
```

```md video https://youtube.com/embed/ITOZkzjtjUA?start=6835&end=8225
# Video: Tutorial of Database Model with Forms, Model Field Changes and Migrations, and adding a DateTime Field
```

## Beyond the built-in ORM

For services such as Airtable, Databricks, or Snowflake, use their Python libraries or REST APIs in your backend. These connections are separate from the relational ORM described above. See the [AI and API integrations overview](/docs/ai/integrations/overview/) for available integrations and custom connection options.

To replace the in-memory data in the [dashboard tutorial](/docs/getting-started/dashboard-tutorial/), query your database into state and persist new records in the form's event handler. Refresh the state after a write so the table and chart display the latest results.

<!-- faqs-start -->
<!-- faqs-visible -->

## FAQ

### Which databases does Reflex support?

The optional Reflex ORM uses SQLModel and SQLAlchemy to connect to MySQL, PostgreSQL, SQL Server, and SQLite. Define tables as Python classes, configure the database URL, and install the appropriate DBAPI driver. Queries run in the Python backend through database sessions.

### Can a Reflex app connect to MySQL, SQL Server, or SQLite instead of PostgreSQL?

Yes. Configure the database URL and driver for your chosen database. Many model and query patterns are portable, but review database-specific types, SQL features, constraints, and migrations when switching engines. Existing data must also be migrated.

### Can Reflex connect to data sources without a prebuilt connector, like Airtable or Databricks?

Yes. A Reflex app can use Python libraries or REST APIs to access Airtable, Databricks, Snowflake, and other services. Keep credentials in the backend, query the service in your application logic, and assign results to state for display.

<!-- faqs-end -->
