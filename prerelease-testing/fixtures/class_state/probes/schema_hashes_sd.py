"""Schema hash of field-configured shapes: set_default (a5) vs .default/.default_factory (a4/0.9.12) must agree.
Run: EXPECT_VENV=<venv> python -I schema_hashes_sd.py"""
import hashlib
import os

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

LATE = []


class HSd(rx.State):
    limit: int = 0
    items: list[str] = LATE
    _cfg: dict = {}


f = HSd.__fields__
if hasattr(f["limit"], "set_default"):
    f["limit"].set_default(10)
    f["items"].set_default(["a"])
    f["_cfg"].set_default(default_factory=lambda: {"k": 1})
    how = "set_default"
else:
    f["limit"].default = 10
    f["items"].default_factory = lambda: ["a"]
    f["_cfg"].default_factory = lambda: {"k": 1}
    how = ".default/.default_factory"
LATE.append("late")
h = hashlib.sha256(repr(HSd._to_schema()).encode()).hexdigest()[:16] if hasattr(HSd, "_to_schema") else "n/a"
print(f"reflex {version('reflex')} ({how}): HSd={h}")
