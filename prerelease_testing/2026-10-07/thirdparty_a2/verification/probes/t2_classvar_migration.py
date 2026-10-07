"""Does the documented replacement (ClassVar) fully restore the 'configure the class later' idiom on every version?"""
from __future__ import annotations

import os
from typing import ClassVar

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
    _client: ClassVar[httpx.Client | None] = None      # string annotation (PEP 563) on purpose
    _plain: ClassVar[str] = "a"
    count: int = 0


def step(label, fn):
    try:
        print(f"  {label:<72} -> {fn()!r}"[:200])
    except Exception as e:  # noqa: BLE001
        print(f"  {label:<72} -> RAISES {type(e).__name__}: {str(e)[:90]}")


c = httpx.Client()
step("Cfg._client = httpx.Client()   (class-level config)", lambda: setattr(Cfg, "_client", c))
step("Cfg._client is c  (class read returns the object)", lambda: Cfg._client is c)
step("fresh instance._client is c  (shared, not copied)", lambda: inst(Cfg)._client is c)
step("Cfg._plain = 'b'; fresh instance._plain", lambda: (setattr(Cfg, "_plain", "b"), inst(Cfg)._plain)[1])
step("'_client' registered as a state Field?", lambda: "_client" in Cfg.get_fields())
step("monkeypatch round trip on ClassVar restores cleanly", lambda: (lambda mp: (mp.setattr(Cfg, "_plain", "zzz"), mp.undo(), Cfg._plain)[2])(__import__("pytest").MonkeyPatch()))
