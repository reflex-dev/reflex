---
title: Add a Database Admin Dashboard to a Reflex App with starlette-admin
meta_description: Mount a starlette-admin dashboard on a Reflex backend with api_transformer, require authentication, and migrate from the removed rx.AdminDash integration.
---

# Admin Dashboard

Reflex no longer ships an admin dashboard. `rx.AdminDash(...)` raises an error
that links here. An admin dashboard
exposes every row of every registered table to whoever can reach it, so it
belongs under your own authentication and deployment rules rather than inside
the framework. You can still run [starlette-admin](https://jowilf.github.io/starlette-admin/)
on the Reflex backend; this page shows how.

## Install starlette-admin

```bash
pip install "reflex[db]" starlette-admin
```

The `db` extra provides SQLModel and `get_engine()`. starlette-admin is a
separate project and is not installed with either.

## Mount the dashboard with `api_transformer`

Build the `Admin` from the engine Reflex already configures from
`rx.Config.db_url`, register a `ModelView` per table, mount it on a
`Starlette` app, and pass that app to
[`api_transformer`](/docs/api-routes/overview/). Reflex serves the
dashboard from the backend at `/admin`.

```python
import os

import reflex as rx
from sqlmodel import Field, SQLModel
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette_admin.contrib.sqla import Admin, ModelView

from reflex.model import get_engine


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str
    email: str


secret_key = os.environ["ADMIN_SECRET_KEY"]

admin_app = Starlette()
admin = Admin(
    get_engine(),
    title="My Admin",
    auth_provider=MyAuthProvider(),
    secret_key=secret_key,
    middlewares=[Middleware(SessionMiddleware, secret_key=secret_key)],
)
admin.add_view(ModelView(User))
admin.mount_to(admin_app)

app = rx.App(api_transformer=admin_app)
```

`get_engine()` reads the database URL from `rxconfig.py`, so the dashboard
sees the same database as your event handlers. Any SQLAlchemy engine works in
its place.

The backend serves the dashboard, so in a deployment with separate frontend
and backend hosts the dashboard lives on the backend host, such as
`https://api.example.com/admin`.

## Require authentication

`Admin()` without `auth_provider` serves unauthenticated read and write access
to every registered table. Always pass an `AuthProvider` (`MyAuthProvider`
above), set a stable `secret_key` so CSRF tokens and sessions survive restarts,
and put the backend behind the same network and session rules as the rest of
your admin tooling.
The starlette-admin [authentication guide](https://jowilf.github.io/starlette-admin/user-guide/auth/)
shows how to implement `login`, `authenticate`, and `logout` against your
own user store, and how to restrict individual views and actions. Its
`AuthProvider` keeps the signed-in user in `request.session`, which needs the
`SessionMiddleware` from the example above. Without it, every admin page,
including the login page, fails with a 500 error.

## Migrating from `rx.AdminDash`

Each field of the old `rx.AdminDash` maps to a direct starlette-admin call.

| `rx.AdminDash(...)` | starlette-admin |
| --- | --- |
| `models=[User, Post]` | `admin.add_view(ModelView(User))`, `admin.add_view(ModelView(Post))` |
| `view_overrides={User: UserView}` | `admin.add_view(UserView(User))` |
| `admin=Admin(...)` | Build the `Admin` yourself, as above |
| (default, no `admin`) | `Admin(get_engine(), auth_provider=...)`, which you must create |

Before:

```python
app = rx.App(
    admin_dash=rx.AdminDash(
        models=[User, Post],
        view_overrides={User: UserView},
    ),
)
```

After:

```python
secret_key = os.environ["ADMIN_SECRET_KEY"]

admin_app = Starlette()
admin = Admin(
    get_engine(),
    auth_provider=MyAuthProvider(),
    secret_key=secret_key,
    middlewares=[Middleware(SessionMiddleware, secret_key=secret_key)],
)
admin.add_view(UserView(User))
admin.add_view(ModelView(Post))
admin.mount_to(admin_app)

app = rx.App(api_transformer=admin_app)
```

The old integration mounted the dashboard at `/admin` as well, so existing
links keep working once the app starts again.
