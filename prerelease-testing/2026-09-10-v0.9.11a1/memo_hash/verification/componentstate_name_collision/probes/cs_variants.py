"""Variants around the ComponentState dynamic-name collision.

Usage: <venv>/bin/python probes/cs_variants.py <venv-name>
"""

import sys

import reflex

VENV = sys.argv[1] if len(sys.argv) > 1 else "smoke"
assert f"/envs/{VENV}/" in reflex.__file__, reflex.__file__
print("reflex", reflex.constants.Reflex.VERSION)

import reflex as rx  # noqa: E402


def make(name: str, module: str):
    """Build a ComponentState subclass with the given __name__/__module__."""

    def get_component(cls, **props):
        return rx.el.div(rx.el.button("inc", on_click=cls.inc), cls.count.to_string())

    ns = {
        "__module__": module,
        "__annotations__": {"count": int},
        "count": 0,
        "inc": rx.event(lambda self: setattr(self, "count", self.count + 1)),
        "get_component": classmethod(get_component),
    }
    return type(rx.ComponentState)(name, (rx.ComponentState,), ns)


def attempt(label, klass):
    try:
        c = klass.create()
        print(f"  {label:34s} ok  -> {c.State.get_full_name().split('.')[-1]}")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  {label:34s} ERR {type(e).__name__}: {str(e)[:90]}")
        return False


print("A) same class created twice (expected fine, n1/n2):")
A = make("Widget", "app.mod_a")
attempt("Widget#1", A)
attempt("Widget#2", A)

print("B) same name, different __module__:")
B1 = make("Gauge", "app.mod_a")
B2 = make("Gauge", "app.mod_b")
attempt("mod_a.Gauge", B1)
attempt("mod_b.Gauge", B2)

print("C) different names, different modules (control):")
C1 = make("DialA", "app.mod_a")
C2 = make("DialB", "app.mod_b")
attempt("mod_a.DialA", C1)
attempt("mod_b.DialB", C2)

print("D) same name, SAME module (two local classes):")
D1 = make("Knob", "app.mod_c")
D2 = make("Knob", "app.mod_c")
attempt("mod_c.Knob (first defn)", D1)
attempt("mod_c.Knob (second defn)", D2)

print("E) after the failure, is the first class still usable?")
attempt("mod_a.Gauge again (n2)", B1)
attempt("mod_b.Gauge retry", B2)
