"""FINDING-024 (2026-08-27) / FINDING-013 (this campaign) re-check.

Does an AttributeError raised inside a CachedVarOperation computation still get
masked as "Attribute _cached_get_all_var_data not found"?
"""
import importlib.metadata as md
import traceback

import reflex as rx

print("reflex", md.version("reflex"))


class Boom:
    def __getattr__(self, name):
        raise AttributeError(f"no such thing: {name}")


class S(rx.State):
    x: int = 0


try:
    # a cached var operation whose computation raises AttributeError
    v = rx.Var.create("x") + Boom()  # type: ignore[operator]
    str(v)
    print("NO EXCEPTION")
except Exception:
    tb = traceback.format_exc()
    print(tb[-1200:])
    print(
        "MASKED"
        if "_cached_get_all_var_data" in tb and "no such thing" not in tb
        else "NOT MASKED"
    )
