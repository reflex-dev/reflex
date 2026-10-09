"""upgrading-to-0-10.md: 'On 0.9, assigning State.__fields__["items"].default = [] was safe, because each instance got a
copy of the default.' Check on 0.9.12 (and a4/a5) for frontend + backend list vars, through rx.State instances and through
a root state tree (as a real session creates them). Run: EXPECT_VENV=<venv> python -I probe_09_default_trap.py"""
import os

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

print("reflex", version("reflex"))


class TrapState(rx.State):
    items: list[str] = []
    _bitems: list[str] = []


TrapState.__fields__["items"].default = []
TrapState.__fields__["_bitems"].default = []
f = TrapState.__fields__["items"]
print("field after .default = []:", f"default={f.default!r} factory={f.default_factory}")


def tree():
    root = rx.State(_reflex_internal_init=True)
    return root.get_substate(TrapState.get_full_name().split(".")[1:])


for label, mk in (("direct instances", lambda: TrapState(_reflex_internal_init=True)), ("session trees (root State)", tree)):
    a, b = mk(), mk()
    a.items.append("leak")
    a._bitems.append("bleak")
    c = mk()
    print(f"{label}: other session items={list(b.items)} _bitems={list(b._bitems)}; new session items={list(c.items)} "
          f"_bitems={list(c._bitems)}; field default now={f.default!r}")
