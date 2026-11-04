---
title: Add a Database Admin Dashboard to a Reflex App with starlette-admin
meta_description: Mount a starlette-admin dashboard on a Reflex backend with api_transformer, require authentication, and migrate from the removed rx.AdminDash integration.
---

# Admin Dashboard

Reflex no longer ships an admin dashboard. `rx.AdminDash` and
`rx.App(admin_dash=...)` raise an error that links here. An admin dashboard
exposes every row of every registered table to whoever can reach it, so it
belongs under your own authentication and deployment rules rather than inside
the framework. You can still run [starlette-admin](https://jowilf.github.io/starlette-admin/)
on the Reflex backend; this page shows how.

## Install starlette-admin

```bash
pip install starlette-admin
```

starlette-admin is a separate project and is not installed with `reflex` or
`reflex[db]`.

## Mount the dashboard with `api_transformer`

Build the `Admin` from the engine Reflex already configures from
`rx.Config.db_url`, register a `ModelView` per table, mount it on a
`Starlette` app, and pass that app to
[`api_transformer`](/docs/api-routes/overview/). Reflex serves the
dashboard from the backend at `/admin`.

```python
import os

import reflex as rx
from starlette.applications import Starlette
from starlette_admin.contrib.sqla import Admin, ModelView

from reflex.model import get_engine


class User(rx.Model, table=True):
    username: str
    email: str


admin_app = Starlette()
admin = Admin(
    get_engine(),
    title="My Admin",
    auth_provider=MyAuthProvider(),
    secret_key=os.environ["ADMIN_SECRET_KEY"],
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
to every registered table. Always pass an `AuthProvider`, set a stable
`secret_key` so CSRF tokens survive restarts, and put the backend behind the
same network and session rules as the rest of your admin tooling.
The starlette-admin [authentication guide](https://jowilf.github.io/starlette-admin/user-guide/authentication/)
shows how to implement `login`, `is_authenticated`, and `logout` against your
own user store, and how to restrict individual views and actions.

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
admin_app = Starlette()
admin = Admin(
    get_engine(),
    auth_provider=MyAuthProvider(),
    secret_key=os.environ["ADMIN_SECRET_KEY"],
)
admin.add_view(UserView(User))
admin.add_view(ModelView(Post))
admin.mount_to(admin_app)

app = rx.App(api_transformer=admin_app)
```

The old integration mounted the dashboard at `/admin` as well, so existing
links keep working once the app starts again.
