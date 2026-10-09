"""#7465 probe: double-underscore attributes in state classes and handlers (backend only).

Usage: python priv_probe.py <venv-name> <dev|prod>
"""
import asyncio
import json
import os
import sys
import traceback

venv, mode = sys.argv[1], sys.argv[2]
os.environ["REFLEX_ENV_MODE"] = mode
import reflex as rx  # noqa: E402

assert f"/envs/{venv}/" in rx.__file__, rx.__file__
import importlib.metadata  # noqa: E402

from reflex.state import State  # noqa: E402

VERSION = importlib.metadata.version("reflex")
RES = {"venv": venv, "mode": mode, "version": VERSION}


def err(e):
    return f"{type(e).__name__}: {str(e)[:240]}"


try:
    class PrivMixin(rx.State, mixin=True):
        __MIX_LIMIT = 2
        mix_out: str = ""

        @rx.event
        def mix_scratch(self, v: str):
            self.__scratch = v
            self.mix_out = f"scratch={self.__scratch} limit={self.__MIX_LIMIT}"

    class PrivA(PrivMixin, rx.State):
        __LIMIT = 3
        __version__ = "v1"
        count: int = 0
        note: str = ""

        @rx.event
        def bump(self):
            if self.count < self.__LIMIT:
                self.count += 1
            self.__last_seen = self.count
            self.note = f"count={self.count} last={self.__last_seen} limit={self.__LIMIT} ver={self.__version__}"

        @rx.event
        def private_only(self, v: str):
            self.__last_seen = v

        @rx.var
        def view_getattr(self) -> str:
            return f"last={getattr(self, '_PrivA__last_seen', 'unset')}"

        @rx.var
        def view_direct(self) -> str:
            try:
                return f"last={self.__last_seen}"
            except AttributeError:
                return "last=unset"

    RES["class_created"] = True
except Exception as e:  # noqa: BLE001
    RES["class_created"] = False
    RES["class_error"] = err(e)
    RES["tb"] = traceback.format_exc()[-800:]
    print(json.dumps(RES))
    sys.exit()

RES["fields"] = sorted(PrivA.get_fields()) if hasattr(PrivA, "get_fields") else None
RES["backend_vars_attr"] = sorted(getattr(PrivA, "backend_vars", {}) or {}) if not VERSION.startswith("0.10") else "n/a"
RES["base_vars"] = sorted(PrivA.base_vars)
RES["computed_vars"] = sorted(PrivA.computed_vars)
RES["class_level_LIMIT"] = repr(getattr(PrivA, "_PrivA__LIMIT", "MISSING"))
RES["class_level_MIX_LIMIT"] = repr(getattr(PrivA, "_PrivMixin__MIX_LIMIT", "MISSING"))
try:
    RES["deps_view_direct"] = {k: sorted(v) for k, v in PrivA.computed_vars["view_direct"]._deps(objclass=PrivA).items()}
except Exception as e:  # noqa: BLE001
    RES["deps_view_direct"] = err(e)
try:
    RES["deps_view_getattr"] = {k: sorted(v) for k, v in PrivA.computed_vars["view_getattr"]._deps(objclass=PrivA).items()}
except Exception as e:  # noqa: BLE001
    RES["deps_view_getattr"] = err(e)

root = State(_reflex_internal_init=True)
s = root.get_substate(PrivA.get_full_name().split(".")[1:])
root._clean()


def step(name, fn, *a):
    try:
        fn(s, *a)
        RES[f"{name}_dirty"] = sorted(s.dirty_vars)
        d = s.get_delta()
        RES[f"{name}_delta"] = d.get(PrivA.get_full_name(), d) if isinstance(d, dict) else d
    except Exception as e:  # noqa: BLE001
        RES[f"{name}_error"] = err(e)
    root._clean()


step("bump", PrivA.bump.fn)
step("bump2", PrivA.bump.fn)
step("private_only", PrivA.private_only.fn, "P")
step("mix_scratch", PrivA.mix_scratch.fn, "S")
RES["note"] = s.note
RES["mix_out"] = s.mix_out
RES["instance_dict_private"] = sorted(k for k in vars(s) if "__" in k and not k.startswith("__"))
RES["in_dict"] = [k for k in json.dumps(s.dict(), default=str).split('"') if "last_seen" in k or "scratch" in k]
import pickle  # noqa: E402

try:
    s2 = pickle.loads(pickle.dumps(s))
    RES["pickle_roundtrip_last_seen"] = repr(getattr(s2, "_PrivA__last_seen", "MISSING"))
    RES["pickle_roundtrip_scratch"] = repr(getattr(s2, "_PrivMixin__scratch", "MISSING"))
except Exception as e:  # noqa: BLE001
    RES["pickle_error"] = err(e)

# explicit rx.field() dunder (a2 feature) -- only meaningful on 0.10.0a2
try:
    class PrivF(rx.State):
        __counter: rx.Field[int] = rx.field(0)

        @rx.event
        def inc(self):
            self.__counter += 1

        @rx.var
        def counter_view(self) -> int:
            return self.__counter

    RES["field_dunder_fields"] = sorted(PrivF.get_fields()) if hasattr(PrivF, "get_fields") else sorted(PrivF.backend_vars)
    root2 = State(_reflex_internal_init=True)
    f = root2.get_substate(PrivF.get_full_name().split(".")[1:])
    root2._clean()
    PrivF.inc.fn(f)
    RES["field_dunder_dirty"] = sorted(f.dirty_vars)
    d = f.get_delta()
    RES["field_dunder_delta"] = d.get(PrivF.get_full_name(), d)
except Exception as e:  # noqa: BLE001
    RES["field_dunder_error"] = err(e)

print(json.dumps(RES, default=str))
