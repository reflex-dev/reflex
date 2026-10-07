"""Python 3.14 lazy annotations: state var annotated with a class defined later in the module.

Usage: <venv>/bin/python pep649_probe.py <expected-venv-substring>
"""
import dataclasses
import importlib.metadata as md
import json
import sys
import traceback

import reflex as rx

assert sys.argv[1] in rx.__file__, rx.__file__
out = {"python": sys.version.split()[0], "reflex": md.version("reflex")}
try:
    class LazyState(rx.State):
        """Annotation names a dataclass defined below (legal under PEP 649)."""

        item: Later | None = None  # noqa: F821
        items: list[Later] = []  # noqa: F821

        @rx.event
        def fill(self):
            self.item = Later(5)
            self.items = [Later(1), Later(2)]

    out["class_creation"] = "ok"
except Exception as e:  # noqa: BLE001
    out["class_creation"] = f"{type(e).__name__}: {e}"
    print(json.dumps(out, indent=1))
    sys.exit(0)


@dataclasses.dataclass
class Later:
    """Defined after the state that uses it."""

    x: int = 1


def attempt(name, fn):
    try:
        out[name] = repr(fn())[:300]
    except Exception as e:  # noqa: BLE001
        out[name] = f"ERR {type(e).__name__}: {str(e)[:300]}"


attempt("field_type item", lambda: LazyState.get_fields()["item"].annotated_type)
attempt("field_type items", lambda: LazyState.get_fields()["items"].annotated_type)
attempt("var item _var_type", lambda: LazyState.item._var_type)
attempt("var item.x (attr access)", lambda: str(LazyState.item.x))
attempt("foreach items -> x", lambda: str(rx.foreach(LazyState.items, lambda i: rx.text(i.x)).render())[:200])
attempt("render text(item.x)", lambda: str(rx.text(LazyState.item.x).render())[:200])


async def run_event():
    from reflex.state import State

    root = State(_reflex_internal_init=True)
    sub = await root.get_state(LazyState)
    sub.fill()
    return root.get_delta()


import asyncio

attempt("event + delta", lambda: asyncio.run(run_event()))
print(json.dumps(out, indent=1))
