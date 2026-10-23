"""Dump the public API surface of reflex_build_sdk as JSON, and probe default_transport().

Run in each sdk venv: EXPECT_VENV=cloud_cli-sdk-new python -I sdk_api_dump.py > api.json
"""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import json
import os
import pkgutil
import sys

import reflex_build_sdk

expect = os.environ["EXPECT_VENV"]
assert f"/envs/{expect}/" in reflex_build_sdk.__file__, reflex_build_sdk.__file__

out: dict = {"version": reflex_build_sdk.__version__ if hasattr(reflex_build_sdk, "__version__") else None}
import importlib.metadata as md

out["dist_version"] = md.version("reflex-build-sdk")
out["installed_http_libs"] = {
    name: importlib.util.find_spec(name) is not None for name in ("httpx", "httpx2", "aiohttp")
}


def signature(obj) -> str:
    try:
        return str(inspect.signature(obj))
    except (TypeError, ValueError):
        return "?"


def describe_module(name: str) -> dict:
    mod = importlib.import_module(name)
    names = getattr(mod, "__all__", None)
    public = {}
    for attr in sorted(names if names is not None else [n for n in dir(mod) if not n.startswith("_")]):
        try:
            obj = getattr(mod, attr)
        except Exception as ex:  # lazy attrs may fail if an optional lib is missing
            public[attr] = f"<getattr failed: {type(ex).__name__}: {ex}>"
            continue
        if inspect.isclass(obj):
            entry: dict = {"kind": "class", "bases": [b.__name__ for b in obj.__bases__]}
            if dataclasses.is_dataclass(obj):
                entry["fields"] = {
                    f.name: {
                        "type": str(f.type),
                        "required": f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING,
                        "json": f.metadata.get("reflex_build_sdk.json_name", f.name),
                    }
                    for f in dataclasses.fields(obj)
                }
            entry["methods"] = {
                n: signature(m)
                for n, m in inspect.getmembers(obj)
                if not n.startswith("_") and (inspect.isfunction(m) or inspect.ismethod(m))
            }
            public[attr] = entry
        elif inspect.isfunction(obj):
            public[attr] = {"kind": "function", "signature": signature(obj)}
        elif inspect.ismodule(obj):
            public[attr] = {"kind": "module"}
        else:
            public[attr] = {"kind": type(obj).__name__, "repr": repr(obj)[:80]}
    return {"__all__": names, "public": public}


modules = ["reflex_build_sdk", "reflex_build_sdk.transports", "reflex_build_sdk.types"]
for info in pkgutil.walk_packages(reflex_build_sdk.__path__, "reflex_build_sdk."):
    if not any(part.startswith("_") for part in info.name.split(".")[1:]):
        if info.name not in modules:
            modules.append(info.name)
out["modules"] = {name: describe_module(name) for name in modules}

# Resource attributes on the clients (apps, auth, ...) and their public methods.
from reflex_build_sdk import AsyncReflexBuild, ReflexBuild  # noqa: E402

for client_cls in (ReflexBuild, AsyncReflexBuild):
    client = client_cls(token="t", base_url="http://127.0.0.1:1")
    resources = {}
    for attr in sorted(a for a in dir(client) if not a.startswith("_")):
        value = getattr(client, attr)
        if hasattr(value, "_client"):
            resources[attr] = {
                n: signature(m) for n, m in inspect.getmembers(value) if not n.startswith("_") and callable(m)
            }
            # nested resources (apps.secrets, auth.tokens, ...)
            for sub in sorted(a for a in dir(value) if not a.startswith("_")):
                subvalue = getattr(value, sub)
                if hasattr(subvalue, "_client"):
                    resources[f"{attr}.{sub}"] = {
                        n: signature(m) for n, m in inspect.getmembers(subvalue) if not n.startswith("_") and callable(m)
                    }
    out[client_cls.__name__] = {"init": signature(client_cls.__init__), "resources": resources}
    if client_cls is ReflexBuild:
        out["ReflexBuild_default_transport_type"] = type(client._transport).__name__
    client.close() if client_cls is ReflexBuild else None

# default_transport() probe
probe: dict = {}
try:
    from reflex_build_sdk import transports

    probe["has_default_transport"] = hasattr(transports, "default_transport")
    probe["in___all__"] = "default_transport" in getattr(transports, "__all__", ())
    if probe["has_default_transport"]:
        t = transports.default_transport()
        probe["returns"] = type(t).__name__
        probe["has_send_close"] = callable(getattr(t, "send", None)) and callable(getattr(t, "close", None))
        probe["distinct_instances"] = transports.default_transport() is not t
        probe["doc"] = (transports.default_transport.__doc__ or "").strip().splitlines()[0]
        probe["signature"] = signature(transports.default_transport)
        # Wrap it the way the hosting CLI does, and send one request through a client that owns nothing.
        from reflex_build_sdk.transports import Request

        class Wrapper:
            def __init__(self, inner):
                self.inner = inner
                self.seen = []

            def send(self, request):
                self.seen.append(request.url)
                return self.inner.send(request)

            def close(self):
                self.inner.close()

        wrapped = Wrapper(transports.default_transport())
        with ReflexBuild(token="t", base_url="http://127.0.0.1:1", transport=wrapped, max_retries=0) as c:
            try:
                c.deployments.regions()
            except Exception as ex:
                probe["wrapped_request_error"] = f"{type(ex).__name__}: {str(ex)[:80]}"
        probe["wrapped_saw"] = wrapped.seen
        t.close()
    probe["async_default_transport_public"] = hasattr(transports, "async_default_transport")
    from reflex_build_sdk.transports import _defaults

    probe["_defaults_names"] = sorted(n for n in dir(_defaults) if not n.startswith("__"))
except Exception as ex:
    probe["error"] = f"{type(ex).__name__}: {ex}"
out["default_transport_probe"] = probe

json.dump(out, sys.stdout, indent=1, sort_keys=True)
