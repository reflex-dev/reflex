"""Is the collision deterministic, or an accident of per-class instance counts?

Usage: <venv>/bin/python probes/cs_interleave.py <venv-name>
"""

import sys

import reflex

VENV = sys.argv[1] if len(sys.argv) > 1 else "smoke"
assert f"/envs/{VENV}/" in reflex.__file__, reflex.__file__
print("reflex", reflex.constants.Reflex.VERSION)

import reflex as rx  # noqa: E402


def make(name: str, module: str):
    ns = {
        "__module__": module,
        "__annotations__": {"count": int},
        "count": 0,
        "inc": rx.event(lambda self: setattr(self, "count", self.count + 1)),
        "get_component": classmethod(lambda cls, **p: rx.el.div(cls.count.to_string())),
    }
    return type(rx.ComponentState)(name, (rx.ComponentState,), ns)


def attempt(label, klass):
    try:
        c = klass.create()
        print(f"  {label:30s} ok  -> {c.State.get_full_name().split('.')[-1]}")
    except Exception as e:  # noqa: BLE001
        print(f"  {label:30s} ERR {type(e).__name__}: {str(e)[:80]}")


X1 = make("Slider", "app.mod_a")
X2 = make("Slider", "app.mod_b")
print("mod_a.Slider once, then mod_b.Slider twice:")
attempt("mod_a.Slider #1", X1)
attempt("mod_b.Slider #1", X2)
attempt("mod_b.Slider #2", X2)
print("=> a same-named twin can silently SUCCEED on a later create,")
print("   sharing nothing with the first: name depends only on per-class count.")
