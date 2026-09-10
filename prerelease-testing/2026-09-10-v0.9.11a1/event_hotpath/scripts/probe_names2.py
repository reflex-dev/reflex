"""Extended offline probes for PR #7025 fast paths (no server needed).

Runs each probe in a fresh subprocess so class-creation errors cannot leak between probes.

    <venv>/bin/python probe_names2.py --out results.jsonl      # run everything
    <venv>/bin/python probe_names2.py --one NAME               # single probe (internal)

Probes:
  fast_set_pruned         : every fast-pathed name a subclass defines is dropped from _fast_attr_names,
                            for the class itself and for a substate that inherits the var.
  child_inherits_shadow   : a var named like a framework attr on a parent, read/written via a child state.
  backend_var_gwt         : backend var `_get_was_touched` (the PR's own test case) inside a real rx.State
                            tree: does get_delta()/_clean() on the ROOT still work?
  mixin_interval          : `_interval_computed_var_names` for a mixin-provided interval var and for an
                            inherited one on a substate; `_expired_computed_vars` via StateProxy-like class.
  component_state_interval: rx.ComponentState.create() twice -> each generated class has the interval name.
  dynamic_route_arg       : setup_dynamic_args({"get_value": ...}) prunes the name for class + substate.
  add_var_after           : add_var("get_delta", ...) on a parent prunes grandchildren.
"""
from __future__ import annotations

import json
import subprocess
import sys
import traceback

PROBES = [
    "fast_set_pruned",
    "child_inherits_shadow",
    "backend_var_gwt",
    "mixin_interval",
    "component_state_interval",
    "dynamic_route_arg",
    "add_var_after",
]


def _mk(name: str, bases, body: dict, ann: dict | None = None):
    body = dict(body)
    body.setdefault("__module__", "probe2_mod")
    body.setdefault("__qualname__", name)
    if ann is not None:
        body["__annotations__"] = ann
    return type(name, bases, body)


def probe(name: str) -> dict:
    out: dict = {"probe": name}
    import reflex as rx

    assert "/envs/" in rx.__file__, rx.__file__
    out["version"] = rx.constants.Reflex.VERSION
    out["python"] = sys.version.split()[0]
    from reflex.state import BaseState, State

    fast = getattr(BaseState, "_fast_attr_names", None)
    out["has_fast_attr_names"] = fast is not None
    try:
        if name == "fast_set_pruned":
            if fast is None:
                out["skipped"] = "no _fast_attr_names on this version"
                return out
            P = _mk("PPar", (State,), {"get_state": "x", "_get_delta": 1}, {"get_state": str, "_get_delta": int})
            C = _mk("PChild", (P,), {})
            out["parent_pruned"] = sorted(BaseState._fast_attr_names - P._fast_attr_names)
            out["child_pruned"] = sorted(BaseState._fast_attr_names - C._fast_attr_names)
            out["ok"] = out["parent_pruned"] == ["get_state"] and out["child_pruned"] == ["get_state"]
            # `_get_delta` is not in the framework set (only `get_delta`), so it must not be pruned
        elif name == "child_inherits_shadow":
            P = _mk("SPar", (State,), {"get_state": "shadow"}, {"get_state": str})
            C = _mk("SChild", (P,), {"child_v": 0}, {"child_v": int})
            root = State(_reflex_internal_init=True)
            c = root.get_substate(C.get_full_name().split(".")[1:])
            p = root.get_substate(P.get_full_name().split(".")[1:])
            out["child_read"] = repr(c.get_state)[:120]
            out["parent_read"] = repr(p.get_state)[:120]
            p.get_state = "changed"
            out["parent_after_set"] = repr(p.get_state)[:120]
            out["child_after_parent_set"] = repr(c.get_state)[:120]
            out["root_delta"] = json.dumps(root.get_delta(), default=str)[:300]
            root._clean()
            out["ok"] = out["child_read"] == "'shadow'" and out["parent_after_set"] == "'changed'" and "changed" in out["root_delta"]
        elif name == "backend_var_gwt":
            S = _mk("GwtState", (State,), {"_get_was_touched": 7, "shown": 0}, {"_get_was_touched": int, "shown": int})
            out["pruned"] = sorted(BaseState._fast_attr_names - S._fast_attr_names) if fast is not None else None
            root = State(_reflex_internal_init=True)
            s = root.get_substate(S.get_full_name().split(".")[1:])
            out["read"] = repr(s._get_was_touched)[:80]
            s._get_was_touched += 1
            s.shown = s._get_was_touched
            out["after"] = repr(s._get_was_touched)[:80]
            out["root_delta"] = json.dumps(root.get_delta(), default=str)[:300]
            root._clean()
            out["dirty_after_clean"] = sorted(s.dirty_vars)
            out["ok"] = out["after"] == "8" and '"shown": 8' in out["root_delta"]
        elif name == "mixin_interval":
            import datetime

            M = _mk("TimeMixin", (State,), {"mixin_tick": rx.var(lambda self: 1, interval=1)}, {})
            # a mixin needs the mixin=True kwarg: build with the metaclass call directly
            M = type("TimeMixin2", (State,), {"__module__": "probe2_mod", "__qualname__": "TimeMixin2",
                                              "mixin_tick": rx.var(interval=datetime.timedelta(seconds=1))(lambda self: 1)},
                     mixin=True)
            S = _mk("MixUser", (M,), {"own_tick": rx.var(interval=1)(lambda self: 2), "plain": rx.var(cache=True)(lambda self: 3)})
            C = _mk("MixChild", (S,), {})
            get = lambda cls: sorted(getattr(cls, "_interval_computed_var_names", frozenset()))  # noqa: E731
            out["user_interval_names"] = get(S)
            out["child_interval_names"] = get(C)
            out["user_computed"] = sorted(S.computed_vars)
            root = State(_reflex_internal_init=True)
            s = root.get_substate(S.get_full_name().split(".")[1:])
            out["expired_fresh"] = sorted(s._expired_computed_vars())
            out["ok"] = (
                (not out["has_fast_attr_names"] or out["user_interval_names"] == ["mixin_tick", "own_tick"])
                and out["expired_fresh"] == ["mixin_tick", "own_tick"]
            )
        elif name == "component_state_interval":
            class Clock(rx.ComponentState):
                base: int = 0

                @rx.var(interval=1)
                def now(self) -> int:
                    return self.base

                @classmethod
                def get_component(cls, **props):
                    return rx.text(cls.now)

            a = Clock.create()
            b = Clock.create()
            sa, sb = a.State, b.State
            get = lambda cls: sorted(getattr(cls, "_interval_computed_var_names", frozenset()))  # noqa: E731
            out["a_interval"] = get(sa)
            out["b_interval"] = get(sb)
            out["distinct_classes"] = sa is not sb
            root = State(_reflex_internal_init=True)
            ia = root.get_substate(sa.get_full_name().split(".")[1:])
            out["expired_a"] = sorted(ia._expired_computed_vars())
            out["ok"] = out["distinct_classes"] and out["expired_a"] == ["now"] and (not out["has_fast_attr_names"] or out["a_interval"] == ["now"] == out["b_interval"])
        elif name == "dynamic_route_arg":
            from reflex_base.constants import RouteArgType

            D = _mk("DynRoot", (State,), {})
            DC = _mk("DynChild", (D,), {})
            D.setup_dynamic_args({"get_value": RouteArgType.SINGLE})
            if fast is not None:
                out["root_has_get_value_fast"] = "get_value" in D._fast_attr_names
                out["child_has_get_value_fast"] = "get_value" in DC._fast_attr_names
            root = State(_reflex_internal_init=True)
            d = root.get_substate(D.get_full_name().split(".")[1:])
            dc = root.get_substate(DC.get_full_name().split(".")[1:])
            out["read_root"] = repr(d.get_value)[:120]
            out["read_child"] = repr(dc.get_value)[:120]
            out["ok"] = (not out["has_fast_attr_names"] or (not out["root_has_get_value_fast"] and not out["child_has_get_value_fast"]))
        elif name == "add_var_after":
            A = _mk("AvRoot", (State,), {})
            B = _mk("AvMid", (A,), {})
            C = _mk("AvLeaf", (B,), {})
            A.add_var("get_delta", int, 5)
            if fast is not None:
                out["pruned"] = {cls.__name__: "get_delta" not in cls._fast_attr_names for cls in (A, B, C)}
            root = State(_reflex_internal_init=True)
            c = root.get_substate(C.get_full_name().split(".")[1:])
            out["leaf_read"] = repr(c.get_delta)[:120]
            out["ok"] = out["leaf_read"] == "5" and (not out["has_fast_attr_names"] or all(out["pruned"].values()))
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"[:400]
        out["trace_tail"] = traceback.format_exc().splitlines()[-4:]
        out["ok"] = False
    return out


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == "--one":
        print(json.dumps(probe(sys.argv[2]), default=str))
        return
    out_path = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    results = []
    for p in PROBES:
        r = subprocess.run(
            [sys.executable, __file__, "--one", p],
            capture_output=True, text=True, timeout=180,
            env={"REFLEX_TELEMETRY_ENABLED": "false", "PATH": "/usr/bin:/bin", "HOME": "/root"},
        )
        try:
            res = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:  # noqa: BLE001
            res = {"probe": p, "ok": False, "crash": r.stderr[-800:], "stdout": r.stdout[-300:]}
        if r.stderr.strip():
            res["stderr_tail"] = r.stderr.strip().splitlines()[-3:]
        results.append(res)
        print(json.dumps(res, default=str), flush=True)
    if out_path:
        with open(out_path, "w") as f:
            for res in results:
                f.write(json.dumps(res, default=str) + "\n")
    print("DONE", sum(1 for r in results if r.get("ok")), "/", len(results), "ok", file=sys.stderr)


if __name__ == "__main__":
    main()
