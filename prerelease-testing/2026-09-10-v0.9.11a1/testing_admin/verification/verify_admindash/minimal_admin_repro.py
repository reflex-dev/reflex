"""Minimal, server-free repro: every rx.AdminDash page raises NoMatchFound.

Run with the app directory as cwd (it needs rxconfig.py), using a venv that has
reflex[db] + starlette-admin:

    cd <app dir> && <venv>/bin/python minimal_admin_repro.py

Prints the ASGI route tree reflex builds and the status of two admin pages.
"""

import json
import sys
import traceback

import reflex as rx
from starlette.routing import Mount
from starlette.testclient import TestClient

assert "/envs/" in rx.__file__, rx.__file__

from admindash.admindash import app  # noqa: E402  (needs cwd == app dir)

asgi = app()  # App.__call__ -> compiles and returns the top-level Starlette app


def describe(route, prefix):
    d = {
        "at": prefix,
        "type": type(route).__name__,
        "name": getattr(route, "name", None),
        "path": getattr(route, "path", None),
        "app_type": f"{type(getattr(route, 'app', None)).__module__}.{type(getattr(route, 'app', None)).__name__}",
        "n_child_routes": len(getattr(route, "routes", []) or []),
    }
    return d


tree = [{"at": "asgi", "type": type(asgi).__name__, "n_routes": len(asgi.routes)}]
for i, r in enumerate(asgi.routes):
    tree.append(describe(r, f"asgi.routes[{i}]"))

# the admin Mount does exist - one level deeper, on app._api
api_mounts = [
    {"path": r.path, "name": r.name, "n_child_routes": len(r.routes)}
    for r in app._api.routes
    if isinstance(r, Mount)
]

statuses = {}
errors = {}
with TestClient(asgi, raise_server_exceptions=False) as c:
    for path in ("/ping", "/admin/", "/admin/widget/list", "/admin/api/widget"):
        r = c.get(path)
        statuses[path] = r.status_code

with TestClient(asgi, raise_server_exceptions=True) as c:
    try:
        c.get("/admin/")
    except Exception as e:  # noqa: BLE001
        errors["/admin/"] = f"{type(e).__name__}: {e}"
        errors["frame"] = traceback.format_exc().strip().splitlines()[-6:]

print(
    json.dumps(
        {
            "reflex": rx.__file__,
            "python": sys.version.split()[0],
            "asgi_tree": tree,
            "app._api mounts": api_mounts,
            "statuses": statuses,
            "errors": errors,
        },
        indent=2,
    )
)
