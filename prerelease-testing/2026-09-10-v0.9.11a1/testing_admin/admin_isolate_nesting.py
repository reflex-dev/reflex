"""Isolate the AdminDash 500: starlette-admin's url_for vs a NESTED mount.

No reflex involved. Starlette >= 1.x resolves `request.url_for` against
`scope["router"]`, which `Router.app()` pins to the OUTERMOST router
(`if "router" not in scope`). starlette-admin's `mount_to()` registers its
Mount on whatever app it is given, so when that app is itself mounted inside
another Starlette app, the outermost router has no "admin:*" names.

    cd /tmp && <venv with starlette-admin + sqlmodel>/bin/python <this>
"""

import json

import sqlalchemy as sa
from sqlalchemy.orm import declarative_base
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route
from starlette.testclient import TestClient
from starlette_admin.contrib.sqla.admin import Admin
from starlette_admin.contrib.sqla.view import ModelView

Base = declarative_base()


class Widget(Base):
    __tablename__ = "widget"
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String)


import tempfile, os
_dbf = os.path.join(tempfile.mkdtemp(), "iso.db")
engine = sa.create_engine(f"sqlite:///{_dbf}")
Base.metadata.create_all(engine)


def build_admin():
    admin = Admin(engine, title="probe")
    admin.add_view(ModelView(Widget))
    return admin


async def hello(request):
    return PlainTextResponse("ok")


out = {}

# A: admin mounted directly on the app that serves the request (documented usage)
flat = Starlette(routes=[Route("/ping", hello)])
build_admin().mount_to(flat)
with TestClient(flat, raise_server_exceptions=False) as c:
    out["flat_ping"] = c.get("/ping").status_code
    out["flat_admin_index"] = c.get("/admin/").status_code
    out["flat_admin_list"] = c.get("/admin/widget/list").status_code

# B: admin mounted on an INNER app, which is itself mounted on an outer app
inner = Starlette(routes=[Route("/ping", hello)])
build_admin().mount_to(inner)
outer = Starlette(routes=[Mount("/", app=inner)])
with TestClient(outer, raise_server_exceptions=False) as c:
    out["nested_ping"] = c.get("/ping").status_code
    out["nested_admin_index"] = c.get("/admin/").status_code
    out["nested_admin_list"] = c.get("/admin/widget/list").status_code

# C: same nesting, but the admin Mount is ALSO registered on the outer router
inner2 = Starlette(routes=[Route("/ping", hello)])
admin2 = build_admin()
admin2.mount_to(inner2)
outer2 = Starlette(routes=[Mount("/", app=inner2)])
outer2.router.routes.insert(
    0, Mount("/admin", app=admin2.app, name=admin2.route_name)
)
with TestClient(outer2, raise_server_exceptions=False) as c:
    out["outerroute_admin_index"] = c.get("/admin/").status_code
    out["outerroute_admin_list"] = c.get("/admin/widget/list").status_code

# D: the reflex shape - the inner app is reached through a bare ASGI callable,
# so the outer Mount has no `.routes` to delegate name resolution to.
inner3 = Starlette(routes=[Route("/ping", hello)])
build_admin().mount_to(inner3)


def middleware_wrapper(app):
    async def wrapped(scope, receive, send):
        await app(scope, receive, send)

    return wrapped


outer3 = Starlette(routes=[Mount("/", app=middleware_wrapper(inner3))])
with TestClient(outer3, raise_server_exceptions=False) as c:
    out["wrapped_ping"] = c.get("/ping").status_code
    out["wrapped_admin_index"] = c.get("/admin/").status_code
    out["wrapped_admin_list"] = c.get("/admin/widget/list").status_code

import starlette  # noqa: E402
import starlette_admin  # noqa: E402

out["starlette"] = starlette.__version__
out["starlette_admin"] = getattr(starlette_admin, "__version__", "?")
print(json.dumps(out, indent=2))
