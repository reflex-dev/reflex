"""Probe how a State subclass behaves when it defines a framework-fast-pathed name.

Run under a given venv (from a neutral cwd):
    <venv>/bin/python probe_names.py            # runs every probe in a subprocess each, prints JSON
    <venv>/bin/python probe_names.py --one KIND NAME   # single probe (used internally)

KIND in {var, backend_var, handler, method, computed}.
"""
from __future__ import annotations

import json
import subprocess
import sys
import traceback

NAMES = [
    "dirty_vars", "dirty_substates", "parent_state", "substates", "router",
    "get_name", "get_fields", "get_value", "get_delta", "get_state", "get_full_name",
    "get_skip_vars", "get_substate", "_was_touched", "_backend_vars", "_clean",
    "_mark_dirty", "_get_was_touched", "_expired_computed_vars",
]
KINDS = ["var", "backend_var", "handler", "method", "computed"]


def one(kind: str, name: str) -> dict:
    import asyncio
    out: dict = {"kind": kind, "name": name}
    try:
        import reflex as rx
        out["reflex_file"] = rx.__file__
        assert "/envs/" in rx.__file__, rx.__file__
        import reflex
        from reflex.state import BaseState
        out["version"] = reflex.constants.Reflex.VERSION
        body: dict = {"__module__": "probe_mod", "__qualname__": f"Probe_{kind}_{name}"}
        ann: dict = {}
        if kind == "var":
            ann[name] = str
            body[name] = "user-value"
        elif kind == "backend_var":
            bname = name if name.startswith("_") else "_" + name
            out["actual_name"] = bname
            ann[bname] = str
            body[bname] = "user-backend-value"
            name = bname
        elif kind == "handler":
            def fn(self):
                self.marker = f"handler-{name}-ran"
            fn.__name__ = name
            fn.__qualname__ = name
            body[name] = rx.event(fn)
            ann["marker"] = str
            body["marker"] = ""
        elif kind == "method":
            def fn(self, *a, **k):
                return "plain-method"
            fn.__name__ = name
            fn.__qualname__ = name
            body[name] = fn
        elif kind == "computed":
            def fn(self) -> str:
                return "computed-value"
            fn.__name__ = name
            fn.__qualname__ = name
            body[name] = rx.var(fn)
        body["__annotations__"] = ann
        cls = type(f"Probe_{kind}_{name}".replace("_", "U"), (rx.State,), body)
        out["class_created"] = True
        out["in_fast_attr_names"] = name in getattr(cls, "_fast_attr_names", frozenset()) if hasattr(cls, "_fast_attr_names") else None
        out["in_vars"] = name in cls.vars
        out["in_backend_vars"] = name in cls.backend_vars
        out["in_event_handlers"] = name in cls.event_handlers
        root = rx.State(_reflex_internal_init=True)
        sub = root.get_substate(cls.get_full_name().split(".")[1:])
        out["instantiated"] = True
        try:
            val = getattr(sub, name)
            out["getattr"] = repr(val)[:160]
        except Exception as e:
            out["getattr_error"] = f"{type(e).__name__}: {e}"[:300]
        if kind in ("var", "backend_var"):
            try:
                setattr(sub, name, "new-value")
                out["setattr"] = "ok"
                out["getattr_after_set"] = repr(getattr(sub, name))[:160]
            except Exception as e:
                out["setattr_error"] = f"{type(e).__name__}: {e}"[:300]
            try:
                d = sub.get_delta()
                out["delta_after_set"] = json.dumps(d, default=str)[:300]
            except Exception as e:
                out["delta_error"] = f"{type(e).__name__}: {e}"[:300]
            try:
                out["dict_has_name"] = name in sub.dict().get(cls.get_full_name(), {})
            except Exception as e:
                out["dict_error"] = f"{type(e).__name__}: {e}"[:300]
        if kind == "handler":
            try:
                h = getattr(sub, name)
                r = h()
                if asyncio.iscoroutine(r):
                    asyncio.run(r)
                out["handler_call"] = repr(getattr(sub, "marker", None))[:160]
            except Exception as e:
                out["handler_call_error"] = f"{type(e).__name__}: {e}"[:300]
        if kind == "method":
            try:
                out["method_call"] = repr(getattr(sub, name)())[:160]
            except Exception as e:
                out["method_call_error"] = f"{type(e).__name__}: {e}"[:300]
        if kind == "computed":
            try:
                out["computed_read"] = repr(getattr(sub, name))[:160]
                out["dict_value"] = repr(sub.dict().get(cls.get_full_name(), {}).get(name))[:160]
            except Exception as e:
                out["computed_error"] = f"{type(e).__name__}: {e}"[:300]
        # Does the framework itself still work on this instance? (a delta from a sibling var)
        try:
            root.get_delta()
            out["framework_ok"] = True
        except Exception as e:
            out["framework_ok"] = f"{type(e).__name__}: {e}"[:300]
    except Exception as e:
        out["class_error"] = f"{type(e).__name__}: {e}"[:400]
        out["trace_tail"] = traceback.format_exc().splitlines()[-3:]
    return out


def main() -> None:
    if len(sys.argv) >= 4 and sys.argv[1] == "--one":
        print(json.dumps(one(sys.argv[2], sys.argv[3]), default=str))
        return
    results = []
    for kind in KINDS:
        for name in NAMES:
            p = subprocess.run(
                [sys.executable, __file__, "--one", kind, name],
                capture_output=True, text=True, timeout=120,
                env={"REFLEX_TELEMETRY_ENABLED": "false", "PATH": "/usr/bin:/bin", "HOME": "/root"},
            )
            try:
                res = json.loads(p.stdout.strip().splitlines()[-1])
            except Exception:
                res = {"kind": kind, "name": name, "crash": p.stderr[-600:], "stdout": p.stdout[-300:]}
            if p.returncode != 0 and "class_error" not in res:
                res["stderr_tail"] = p.stderr[-400:]
            results.append(res)
            print(json.dumps(res, default=str), flush=True)
    print("DONE", len(results), file=sys.stderr)


if __name__ == "__main__":
    main()
