"""Check whether rxe's redact_router_session() still finds the router var in a state dict.

Usage: python probe_router_redact.py <venv-marker>
Run from a neutral cwd (NOT the reflex checkout).
"""

import os
import sys

os.environ["CI"] = "true"
os.environ["REFLEX_TELEMETRY_ENABLED"] = "false"

import reflex  # noqa: E402

assert sys.argv[1] in reflex.__file__, reflex.__file__
print("REFLEX", reflex.__file__)

import reflex as rx  # noqa: E402
from reflex.istate.data import RouterData  # noqa: E402
from reflex.state import State  # noqa: E402
from reflex_enterprise.plugins.event_handler_api import (  # noqa: E402
    redact_router_session,
    router_data_for_token,
)


class Probe(rx.State):
    """Trivial app state."""

    n: int = 0


st = State(_reflex_internal_init=True)
rd = router_data_for_token(
    "SECRET-CLIENT-TOKEN", headers={"host": "x"}, query={"a": "1"}, path="/tickets"
)
st.router_data = dict(rd)
st.router = RouterData.from_router_data(st.router_data)

print("--- self.router readback ---")
print("  client_token:", st.router.session.client_token)
print("  url         :", st.router.url)
print("  page.params :", st.router.page.params)
print("  url.qparams :", st.router.url.query_parameters)
print("  headers.host:", st.router.headers.host)

d = st.dict()
print("--- state dict (top level) ---")
for k, v in d.items():
    if isinstance(v, dict):
        print(f"  {k}:")
        for kk in sorted(v):
            if isinstance(v[kk], dict):
                continue
            print(f"      {kk} = {str(v[kk])[:90]}")
    else:
        print(f"  {k} = {str(v)[:90]}")

red = redact_router_session(d)


def find_token(obj, path="") -> list[str]:
    import dataclasses

    hits = []
    obj = getattr(obj, "__wrapped__", obj)
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            hits += find_token(getattr(obj, f.name), f"{path}.{f.name}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            hits += find_token(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            hits += find_token(v, f"{path}[{i}]")
    else:
        s = getattr(obj, "__wrapped__", obj)
        if isinstance(s, str) and "SECRET-CLIENT-TOKEN" in s:
            hits.append(path)
    return hits


leaks = find_token(red)
print("--- after redact_router_session() ---")
print("  SECRET-CLIENT-TOKEN still present at:", leaks or "NOWHERE (redacted ok)")
print("VERDICT", "LEAK" if leaks else "OK")
