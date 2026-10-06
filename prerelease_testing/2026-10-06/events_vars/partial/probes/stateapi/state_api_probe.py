"""Backend-level State API edge cases (run with alpha or stable venv, from this neutral dir).

Usage: python state_api_probe.py <venv-name> [dev|prod]
Each check is isolated; results print as one JSON line per check.
"""
import json
import os
import sys
import traceback

venv = sys.argv[1]
mode = sys.argv[2] if len(sys.argv) > 2 else "dev"
ONLY = sys.argv[3] if len(sys.argv) > 3 else None
os.environ["REFLEX_ENV_MODE"] = mode
import reflex as rx  # noqa: E402

assert f"/scratchpad/envs/{venv}/" in rx.__file__, rx.__file__
import importlib.metadata  # noqa: E402

from reflex.state import State  # noqa: E402

VERSION = importlib.metadata.version("reflex")


def out(name, **kw):
    print(json.dumps({"check": name, "venv": venv, "mode": mode, "version": VERSION, **kw}, default=str), flush=True)


def err(e):
    return f"{type(e).__name__}: {str(e)[:300]}"


def substate(cls):
    root = State(_reflex_internal_init=True)
    path = cls.get_full_name().split(".")[1:]
    return root.get_substate(path), root


def check(fn):
    if ONLY is not None and fn.__name__ != ONLY:
        return fn
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        out(fn.__name__, error=err(e), tb=traceback.format_exc()[-600:])
    return fn


@check
def shadowed_get_fields():
    class ShParent(rx.State):
        shared: str = "parent"
        _bshared: int = 1

    class ShChild(ShParent):
        shared: str = "child"
        _bshared: int = 2

    pf, cf = ShParent.get_fields(), ShChild.get_fields()
    root = State(_reflex_internal_init=True)
    p = root.get_substate(ShParent.get_full_name().split(".")[1:])
    c = root.get_substate(ShChild.get_full_name().split(".")[1:])
    out("shadowed_get_fields",
        parent_field_owner=getattr(pf["shared"], "_owner", None).__name__ if getattr(pf["shared"], "_owner", None) else None,
        child_field_owner=getattr(cf["shared"], "_owner", None).__name__ if getattr(cf["shared"], "_owner", None) else None,
        same_field_object=pf["shared"] is cf["shared"],
        child_fields_count_shared=sum(1 for k in cf if k == "shared"),
        parent_value=p.shared, child_value=c.shared,
        backend_parent=p._bshared, backend_child=c._bshared,
        child_dict=c.dict().get(ShChild.get_full_name()),
        parent_vars_js=str(ShParent.shared), child_vars_js=str(ShChild.shared))


@check
def init_override():
    class InitState(rx.State):
        x: int = 1

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._init_ran = True

    s, _ = substate(InitState)
    out("init_override", x=s.x, init_ran=getattr(s, "_init_ran", None))


@check
def slots_state():
    try:
        class SlotState(rx.State):
            __slots__ = ("extra",)
            x: int = 1
        s, _ = substate(SlotState)
        s.extra = 5
        out("slots_state", created=True, extra=s.extra, x=s.x)
    except Exception as e:  # noqa: BLE001
        out("slots_state", created=False, error=err(e))


for _name in ["items", "dict", "reset", "router", "setvar", "get_state", "substates", "parent_state",
              "dirty_vars", "get_value", "is_hydrated", "event_handlers", "vars", "fields"]:
    def _make(nm):
        def method_named_var():
            try:
                cls = type(f"Named_{nm}", (rx.State,), {"__annotations__": {nm: int}, nm: 1, "__module__": __name__})
            except Exception as e:  # noqa: BLE001
                out(f"var_named_{nm}", class_created=False, error=err(e))
                return
            info = {"class_created": True}
            try:
                s, _ = substate(cls)
                info["instance_value"] = repr(getattr(s, nm))[:80]
                try:
                    setattr(s, nm, 2)
                    info["after_set"] = repr(getattr(s, nm))[:80]
                except Exception as e:  # noqa: BLE001
                    info["set_error"] = err(e)
                try:
                    info["dict_ok"] = bool(s.dict())
                except Exception as e:  # noqa: BLE001
                    info["dict_error"] = err(e)
                try:
                    s.reset()
                    info["reset_ok"] = True
                except Exception as e:  # noqa: BLE001
                    info["reset_error"] = err(e)
            except Exception as e:  # noqa: BLE001
                info["instance_error"] = err(e)
            try:
                info["class_attr"] = str(getattr(cls, nm))[:120]
            except Exception as e:  # noqa: BLE001
                info["class_attr_error"] = err(e)
            out(f"var_named_{nm}", **info)
        method_named_var.__name__ = f"var_named_{nm}"
        return method_named_var
    check(_make(_name))


@check
def undeclared_assignment():
    class Undecl(rx.State):
        x: int = 1

    s, root = substate(Undecl)
    try:
        s.undeclared_attr = 42
        assigned = True
        error = None
    except Exception as e:  # noqa: BLE001
        assigned = False
        error = err(e)
    d = json.dumps(s.dict(), default=str)
    delta = None
    try:
        delta = s.get_delta()
    except Exception as e:  # noqa: BLE001
        delta = err(e)
    import pickle
    try:
        s2 = pickle.loads(pickle.dumps(s))
        survives_pickle = getattr(s2, "undeclared_attr", "MISSING")
    except Exception as e:  # noqa: BLE001
        survives_pickle = err(e)
    out("undeclared_assignment", assigned=assigned, error=error, in_dict="undeclared_attr" in d,
        in_delta="undeclared_attr" in json.dumps(delta, default=str), dirty_vars=sorted(s.dirty_vars),
        hasattr=hasattr(s, "undeclared_attr"), survives_pickle=survives_pickle)


@check
def compile_time_setvar_backend_name():
    class SV(rx.State):
        pub: str = ""
        _secret: str = ""

    res = {}
    for name in ["pub", "_secret", "nonexistent", "is_hydrated", "router"]:
        try:
            spec = SV.setvar(name, "x")
            res[name] = "allowed"
        except Exception as e:  # noqa: BLE001
            res[name] = err(e)
    out("compile_time_setvar", **res)


@check
def late_supersedes_marker():
    class LS(rx.State):
        def h(self):
            pass

    before = LS.h.supersedes
    setattr(LS.h.fn, "_reflex_supersedes", True)
    after = LS.h.supersedes
    out("late_supersedes_marker_after_read", before=before, after=after)


@check
def background_marker_without_read():
    class LB(rx.State):
        async def h(self):
            pass

    _ = LB.h
    setattr(LB.h.fn, "_reflex_background_task", True)
    out("late_background_marker_no_prior_read", is_background=LB.h.is_background)


@check
def self_handler_instance_access():
    class HP(rx.State):
        n: int = 0

        def bump(self):
            self.n += 1

        def _kind(self):
            return "parent"

        def kind_report(self):
            return self._kind()

    class HC(HP):
        def _kind(self):
            return "child"

    c, root = substate(HC)
    bound = c.bump
    out("instance_handler_access", bound_type=type(bound).__name__,
        bound_self=type(getattr(bound, "__self__", getattr(bound, "args", [None])[0] if hasattr(bound, "args") else None)).__name__,
        kind_via_child_instance=c.kind_report())


@check
def telemetry_walk_then_late_marker():
    """Does an app compile (with telemetry enabled) cache is_background before a late marker?"""
    from reflex_base.event import EventHandler  # noqa: F401
    class TB(rx.State):
        async def h(self):
            pass

    from reflex.utils import telemetry_accounting  # alpha only
    from reflex_base.telemetry_context import TelemetryContext
    app = rx.App()
    app.add_page(lambda: rx.text("x"), route="/tb")
    feats = {}
    telemetry_accounting._walk_state_features(feats, [TB])
    setattr(TB.h.fn, "_reflex_background_task", True)
    out("telemetry_walk_then_late_marker", background_count_seen=feats.get("background_event_handlers_count"), is_background_after_marker=TB.h.is_background)
