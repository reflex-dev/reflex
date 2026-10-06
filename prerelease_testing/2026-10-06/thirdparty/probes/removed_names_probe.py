"""Probe the names removed/changed in reflex 0.10.0a1 the way a third-party author would.

Usage: <venv>/bin/python removed_names_probe.py <expected-venv-name>
Prints one line per probe: OK <repr> | EXC <type>: <message>.
"""
import json
import os
import sys
import traceback

EXPECTED = sys.argv[1]
os.environ.setdefault("REFLEX_TELEMETRY_ENABLED", "false")
import reflex as rx

assert f"/scratchpad/envs/{EXPECTED}/" in rx.__file__, rx.__file__

results = {}


def probe(label, fn):
    try:
        val = fn()
        r = repr(val)
        results[label] = {"ok": True, "value": r[:300], "type": type(val).__name__}
    except BaseException as e:  # noqa: BLE001
        results[label] = {
            "ok": False,
            "exc": f"{type(e).__module__}.{type(e).__qualname__}",
            "msg": str(e)[:600],
            "mentions_get_fields": "get_fields" in str(e),
            "where": traceback.extract_tb(e.__traceback__)[-1].filename.split("site-packages/")[-1]
            + f":{traceback.extract_tb(e.__traceback__)[-1].lineno}",
        }


class Parent(rx.State):
    a: int = 1
    _b: int = 2

    @rx.var
    def c(self) -> int:
        return self.a + 1


class Child(Parent):
    d: str = "x"
    _e: list[int] = []


def _exec(src):
    ns = {}
    exec(src, ns)  # noqa: S102
    return ns.get("RESULT")


probe("from reflex.constants import CustomComponents", lambda: _exec("from reflex.constants import CustomComponents as RESULT"))
probe("from reflex_base.constants import CustomComponents", lambda: _exec("from reflex_base.constants import CustomComponents as RESULT"))
probe("rx.constants.CustomComponents", lambda: rx.constants.CustomComponents)
probe("Child.backend_vars", lambda: Child.backend_vars)
probe("Child.inherited_vars", lambda: Child.inherited_vars)
probe("Child.inherited_backend_vars", lambda: Child.inherited_backend_vars)
probe("Child.get_skip_vars()", lambda: Child.get_skip_vars())
probe("Child.base_vars", lambda: sorted(Child.base_vars))
probe("Child.vars", lambda: sorted(Child.vars))
probe("Child.computed_vars", lambda: sorted(Child.computed_vars))
probe("Child.event_handlers", lambda: sorted(Child.event_handlers))
probe("Child.get_fields() keys", lambda: sorted(Child.get_fields()))
probe("Child.__fields__ keys", lambda: sorted(Child.__fields__))
probe("Child.get_fields()['_e'] backend attr", lambda: getattr(Child.get_fields()["_e"], "_backend", "<no _backend attr>"))
probe("Child.get_fields()['a'] owner attr", lambda: getattr(Child.get_fields()["a"], "_owner", "<no _owner attr>"))


def make_instance():
    root = rx.State(_reflex_internal_init=True)
    return root.get_substate(Child.get_full_name().split(".")[1:])


probe("instance(Child)", lambda: type(make_instance()).__name__)
probe("instance._backend_vars", lambda: make_instance()._backend_vars)
probe("instance._e", lambda: make_instance()._e)
probe("instance._b (inherited backend)", lambda: make_instance()._b)
probe("instance.get_value('_e')", lambda: make_instance().get_value("_e"))
probe("instance.get_value('a')", lambda: make_instance().get_value("a"))
probe("instance.dict() keys", lambda: sorted(make_instance().dict()))
probe("reflex_base.utils.types.is_backend_base_variable", lambda: _exec("from reflex_base.utils.types import is_backend_base_variable as RESULT"))
probe("reflex.utils.types.is_backend_base_variable", lambda: _exec("from reflex.utils.types import is_backend_base_variable as RESULT"))
probe("reflex_base.utils.types.RESERVED_BACKEND_VAR_NAMES", lambda: _exec("from reflex_base.utils.types import RESERVED_BACKEND_VAR_NAMES as RESULT"))
probe("reflex.utils.types.RESERVED_BACKEND_VAR_NAMES", lambda: _exec("from reflex.utils.types import RESERVED_BACKEND_VAR_NAMES as RESULT"))
probe("reflex.istate.proxy.is_mutable_type", lambda: _exec("from reflex.istate.proxy import is_mutable_type as RESULT"))
probe("reflex_base.utils.types.is_mutable_type", lambda: _exec("from reflex_base.utils.types import is_mutable_type as RESULT"))
probe("is_mutable_type(list)", lambda: _exec("from reflex.istate.proxy import is_mutable_type\nRESULT = is_mutable_type(list)"))
probe("PageContext.get() outside", lambda: _exec("from reflex_base.plugins.compiler import PageContext\nRESULT = PageContext.get()"))
probe("CompileContext.get() outside", lambda: _exec("from reflex_base.plugins.compiler import CompileContext\nRESULT = CompileContext.get()"))
probe("PageContext.get() outside caught as RuntimeError (old style)", lambda: _exec(
    "from reflex_base.plugins.compiler import PageContext\ntry:\n    PageContext.get()\n    RESULT='no error'\nexcept RuntimeError as e:\n    RESULT='caught RuntimeError: '+str(e)\n"))
probe("Child._b class-level", lambda: Child._b)
probe("Child._e class-level", lambda: Child._e)
probe("Child.a class-level", lambda: Child.a)

print(json.dumps(results, indent=1))
