"""T-2 sub-observation: class-level assignment of a live, non-deep-copyable object to a permissive slot."""
import os, threading
from typing import Any
import httpx
import reflex as rx
assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version
print("reflex", version("reflex"))


def inst(cls):
    try:
        return cls(_reflex_internal_init=True)
    except TypeError:
        return cls()


class Cfg(rx.State):
    _any: Any = None
    _http: httpx.Client | None = None
    _lock: Any = None
    _classvar_style_ok: int = 0


def step(label, fn):
    try:
        print(f"  {label:<70} -> {fn()!r}"[:200])
    except Exception as e:  # noqa: BLE001
        print(f"  {label:<70} -> RAISES {type(e).__name__}: {str(e)[:90]}")


client = httpx.Client()
step("Cfg._http = httpx.Client()   (assignment)", lambda: setattr(Cfg, "_http", client))
step("inst = Cfg()  (construct instance)", lambda: type(inst(Cfg)).__name__)
step("inst()._http  (first read)", lambda: type(inst(Cfg)._http).__name__)
step("inst()._http is client (shared object?)", lambda: inst(Cfg)._http is client)
step("Cfg._lock = threading.Lock()  (Any slot)", lambda: setattr(Cfg, "_lock", threading.Lock()))
step("inst()._lock  (first read)", lambda: type(inst(Cfg)._lock).__name__)
