"""Walk the reflex ASGI route tree to show where the starlette-admin Mount lands.

    cd <app dir> && <venv>/bin/python <this>
"""

import json

import reflex

assert "/envs/" in reflex.__file__ and "/home/user/reflex/" not in reflex.__file__, (
    reflex.__file__
)

from reflex.utils.prerequisites import get_and_validate_app  # noqa: E402

app, _mod = get_and_validate_app(reload=False)
asgi = app()


def describe(obj, depth=0, path="asgi"):
    rows = []
    routes = getattr(obj, "routes", None)
    rows.append({
        "path": path,
        "type": type(obj).__module__ + "." + type(obj).__name__,
        "name": getattr(obj, "name", None),
        "mount_path": getattr(obj, "path", None),
        "has_routes_attr": routes is not None,
        "n_routes": len(routes) if routes is not None else None,
    })
    if depth >= 4 or routes is None:
        return rows
    for i, r in enumerate(routes):
        rows += describe(r, depth + 1, f"{path}.routes[{i}]")
        sub = getattr(r, "app", None)
        if sub is not None and not callable(getattr(sub, "routes", None)):
            rows += describe(sub, depth + 1, f"{path}.routes[{i}].app")
    return rows


out = {
    "reflex": reflex.constants.Reflex.VERSION,
    "asgi_type": type(asgi).__module__ + "." + type(asgi).__name__,
    "api_type": type(app._api).__module__ + "." + type(app._api).__name__,
    "api_route_names": [
        (type(r).__name__, getattr(r, "path", None), getattr(r, "name", None))
        for r in app._api.routes
    ],
    "tree": describe(asgi),
}
print(json.dumps(out, indent=2, default=str))
