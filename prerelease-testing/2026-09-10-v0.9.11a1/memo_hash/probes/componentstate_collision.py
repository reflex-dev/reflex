"""Minimal repro: two same-named rx.ComponentState subclasses in different modules.

Usage: <venv>/bin/python probes/componentstate_collision.py <venv-name>
"""

import sys
import types

import reflex

VENV = sys.argv[1] if len(sys.argv) > 1 else "smoke"
assert f"/envs/{VENV}/" in reflex.__file__, reflex.__file__
print("reflex", reflex.constants.Reflex.VERSION, reflex.__file__)

import reflex as rx  # noqa: E402

SRC = """
import reflex as rx

class Counter(rx.ComponentState):
    count: int = 0

    @rx.event
    def inc(self):
        self.count += 1

    @classmethod
    def get_component(cls, **props):
        return rx.el.div(rx.el.button("inc", on_click=cls.inc), cls.count.to_string())
"""

mods = {}
for name in ("pkg_one", "pkg_two"):
    m = types.ModuleType(name)
    m.__file__ = f"/tmp/{name}.py"
    sys.modules[name] = m
    exec(compile(SRC, f"/tmp/{name}.py", "exec"), m.__dict__)
    mods[name] = m

print("class ids:", id(mods["pkg_one"].Counter), id(mods["pkg_two"].Counter))
try:
    c1 = mods["pkg_one"].Counter.create()
    print("first  ok ->", c1.State.get_full_name())
except Exception as e:
    print("first  ERR", type(e).__name__, e)
try:
    c2 = mods["pkg_two"].Counter.create()
    print("second ok ->", c2.State.get_full_name())
except Exception as e:
    print("second ERR", type(e).__name__, e)
