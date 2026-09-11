"""Reflex-free isolation of the /admin 500: which ASGI nesting shapes break starlette-admin's url_for.

Run from a neutral cwd with a venv that has starlette >= 1.x + starlette-admin + sqlmodel + httpx.
"""

import json
import sys

import starlette
import starlette_admin
from sqlalchemy import create_engine
from sqlmodel import Field, SQLModel
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient
from starlette_admin.contrib.sqla.admin import Admin
from starlette_admin.contrib.sqla.view import ModelView

assert "/envs/" in starlette.__file__, starlette.__file__


class Widget(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = ""


import tempfile, pathlib
_dbdir = tempfile.mkdtemp(prefix="iso_admin_")
engine = create_engine(f"sqlite:///{pathlib.Path(_dbdir) / 'iso.db'}")
SQLModel.metadata.create_all(engine)


def make_admin():
    admin = Admin(engine, title="t")
    admin.add_view(ModelView(Widget))
    return admin


def probe(app, label):
    out = {"shape": label}
    with TestClient(app, raise_server_exceptions=False) as c:
        for path in ("/admin/", "/admin/widget/list"):
            r = c.get(path)
            out[path] = r.status_code
    return out


results = []

# A: admin mounted directly on the served app
a = Starlette()
make_admin().mount_to(a)
results.append(probe(a, "A direct mount_to(served app)"))

# B: admin on an inner Starlette, outer mounts the inner OBJECT at ''
inner = Starlette()
make_admin().mount_to(inner)
outer = Starlette(routes=[Mount("", app=inner)])
results.append(probe(outer, "B outer Mount('', app=<Starlette object>)"))

# C: reflex's shape - outer mounts a bare async FUNCTION wrapping the inner app
inner2 = Starlette()
make_admin().mount_to(inner2)


def context_middleware(app):
    async def mw(scope, receive, send):
        await app(scope, receive, send)

    return mw


outer2 = Starlette(routes=[Mount("", app=context_middleware(inner2))])
results.append(probe(outer2, "C outer Mount('', app=<plain function>)  [reflex shape]"))

# D: same wrapper but exposing .routes so Mount.routes can delegate
inner3 = Starlette()
make_admin().mount_to(inner3)


class ContextMiddleware:
    def __init__(self, app):
        self.app = app

    @property
    def routes(self):
        return getattr(self.app, "routes", [])

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)


outer3 = Starlette(routes=[Mount("", app=ContextMiddleware(inner3))])
results.append(probe(outer3, "D outer Mount('', app=<callable exposing .routes>)  [candidate fix]"))

print(
    json.dumps(
        {
            "python": sys.version.split()[0],
            "starlette": starlette.__version__,
            "starlette_admin": starlette_admin.__version__,
            "results": results,
        },
        indent=2,
    )
)
