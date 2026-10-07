"""T-1 matrix: patch a State class var default, then undo, across var kinds x patch mechanisms.

Independent verifier probe (authored without reading the explorer's probes).

Run: REFLEX_TELEMETRY_ENABLED=false EXPECT_VENV=<venv dir name> <venv>/bin/python -I t1_matrix.py [out.json]
"""

import json
import os
import sys
import traceback
from typing import Any, ClassVar
from unittest import mock

import pytest
import reflex as rx

EXPECT = os.environ["EXPECT_VENV"]
assert f"/envs/{EXPECT}/" in rx.__file__, rx.__file__

from importlib.metadata import version  # noqa: E402

REFLEX_VERSION = version("reflex")


def inst(cls):
    """Create a fresh state instance the way unit tests do."""
    try:
        return cls(_reflex_internal_init=True)
    except TypeError:
        return cls()


def _plain(v):
    """Make a comparable/printable plain value (Var/Field objects become 'Type:repr')."""
    v = getattr(v, "__wrapped__", v)
    if isinstance(v, (int, float, str, bool, type(None))):
        return v
    if isinstance(v, (list, tuple, dict, set)):
        return v
    return f"<{type(v).__name__}:{str(v)[:50]}>"


def effective_default(cls, name):
    """What a brand new instance reads (or the exception name)."""
    try:
        return _plain(getattr(inst(cls), name))
    except Exception as e:  # noqa: BLE001
        return f"<{type(e).__name__}: {str(e)[:80]}>"


def field_default(cls, name):
    """The registered Field's default (None-safe)."""
    try:
        f = cls.get_fields()[name]
    except Exception as e:  # noqa: BLE001
        return f"<get_fields: {type(e).__name__}>"
    try:
        return _plain(f.default_value())
    except Exception:  # noqa: BLE001
        d = getattr(f, "default", "?")
        fac = getattr(f, "default_factory", None)
        return _plain(d) if fac is None or str(d) != "MISSING" else f"factory:{fac!r}"[:60]


def class_dict_kind(cls, name):
    v = cls.__dict__.get(name, "<absent>")
    return v if isinstance(v, str) else type(v).__name__


# ---------------------------------------------------------------- var kinds
def k_private():
    class S(rx.State):
        _v: int = 5

    return S, "_v", 99


def k_public():
    class S(rx.State):
        v: int = 5

    return S, "v", 99


def k_rxfield_public():
    class S(rx.State):
        v: int = rx.field(default=5)

    return S, "v", 99


def k_rxfield_private():
    class S(rx.State):
        _v: int = rx.field(default=5)

    return S, "_v", 99


def k_unannot_private():
    class S(rx.State):
        _v = 5

    return S, "_v", 99


def k_unannot_public():
    class S(rx.State):
        v = 5

    return S, "v", 99


def k_mutable_private():
    class S(rx.State):
        _v: list[int] = [1]

    return S, "_v", [99]


def k_factory_private():
    class S(rx.State):
        _v: list[int] = rx.field(default_factory=lambda: [1])

    return S, "_v", [99]


def k_annotation_excludes_none_default():
    class S(rx.State):
        _v: int = None  # type: ignore[assignment]  # sloppy-but-common: annotation excludes the None default

    return S, "_v", 99


def k_optional_none_default():
    from typing import Optional

    class S(rx.State):
        _v: Optional[int] = None

    return S, "_v", 99


def k_mixin_private():
    class M(rx.State, mixin=True):
        _v: int = 5

    class S(M, rx.State):
        pass

    return S, "_v", 99


def k_mixin_public():
    class M(rx.State, mixin=True):
        v: int = 5

    class S(M, rx.State):
        pass

    return S, "v", 99


def k_substate_patch_child():
    class P(rx.State):
        _v: int = 5

    class C(P):
        pass

    return C, "_v", 99


_CS_COUNTER = [0]


def _make_cs(annotations, defaults):
    """Create a uniquely named ComponentState subclass (the generated state is named after it)."""
    import types

    _CS_COUNTER[0] += 1

    def body(ns):
        ns["__module__"] = __name__
        ns["__annotations__"] = dict(annotations)
        ns.update(defaults)
        ns["get_component"] = classmethod(lambda cls, **props: rx.box())

    return types.new_class(f"UniqueCS{_CS_COUNTER[0]}", (rx.ComponentState,), {}, body)


def k_componentstate_private():
    CS = _make_cs({"_v": int, "v": int}, {"_v": 5, "v": 5})
    comp = CS.create()
    return comp.State, "_v", 99


def k_componentstate_public():
    CS = _make_cs({"v": int}, {"v": 5})
    comp = CS.create()
    return comp.State, "v", 99


KINDS = {
    "private annotated (_v: int = 5)": k_private,
    "public annotated (v: int = 5)": k_public,
    "rx.field public (v: int = rx.field(default=5))": k_rxfield_public,
    "rx.field private (_v: int = rx.field(default=5))": k_rxfield_private,
    "unannotated private (_v = 5)": k_unannot_private,
    "unannotated public (v = 5)": k_unannot_public,
    "mutable default private (_v: list[int] = [1])": k_mutable_private,
    "default_factory private (rx.field(default_factory))": k_factory_private,
    "annotation excludes None default (_v: int = None)": k_annotation_excludes_none_default,
    "Optional[int] = None (_v: Optional[int] = None)": k_optional_none_default,
    "mixin private (patch S._v)": k_mixin_private,
    "mixin public (patch S.v)": k_mixin_public,
    "substate private (patch Child._v, declared on Parent)": k_substate_patch_child,
    "ComponentState private (generated state)": k_componentstate_private,
    "ComponentState public (generated state)": k_componentstate_public,
}


# ---------------------------------------------------------------- mechanisms
def m_monkeypatch(cls, name, value):
    mp = pytest.MonkeyPatch()
    mp.setattr(cls, name, value)
    return mp.undo


def m_mock_patch_object(cls, name, value):
    p = mock.patch.object(cls, name, value)
    p.start()
    return p.stop


def m_manual_dict_restore(cls, name, value):
    old = cls.__dict__[name]
    setattr(cls, name, value)

    def undo():
        setattr(cls, name, old)

    return undo


def m_manual_getattr_restore(cls, name, value):
    old = getattr(cls, name)
    setattr(cls, name, value)

    def undo():
        setattr(cls, name, old)

    return undo


def m_manual_original_value(cls, name, value):
    old = effective_default(cls, name)
    old = old if not isinstance(old, list) else list(old)
    setattr(cls, name, value)

    def undo():
        setattr(cls, name, old)

    return undo


def m_monkeypatch_field_default(cls, name, value):
    # workaround candidate: patch the Field object's `default` attribute, not the class
    f = cls.get_fields()[name]
    mp = pytest.MonkeyPatch()
    mp.setattr(f, "default", value)
    return mp.undo


def m_monkeypatch_delattr(cls, name, value):
    mp = pytest.MonkeyPatch()
    mp.delattr(cls, name)
    return mp.undo


def m_monkeypatch_instance(cls, name, value):
    # control: patch a state INSTANCE rather than the class
    i = inst(cls)
    mp = pytest.MonkeyPatch()
    mp.setattr(i, name, value)
    cls.__verifier_instance__ = i  # keep for observation
    return mp.undo


MECHS = {
    "monkeypatch.setattr(cls,name,v)": m_monkeypatch,
    "mock.patch.object(cls,name,v)": m_mock_patch_object,
    "manual: old=cls.__dict__[n]; set; set(old)": m_manual_dict_restore,
    "manual: old=getattr(cls,n); set; set(old)": m_manual_getattr_restore,
    "manual: old=<original value>; set; set(old)": m_manual_original_value,
    "monkeypatch.setattr(Field,'default',v)  [workaround?]": m_monkeypatch_field_default,
    "monkeypatch.delattr(cls,name)": m_monkeypatch_delattr,
}


def run_one(kind_label, kind_fn, mech_label, mech_fn):
    row = {"kind": kind_label, "mech": mech_label}
    try:
        cls, name, value = kind_fn()
    except Exception as e:  # noqa: BLE001
        row["setup_error"] = f"{type(e).__name__}: {str(e)[:150]}"
        return row
    row["before"] = {
        "inst": effective_default(cls, name),
        "field": field_default(cls, name),
        "dict": class_dict_kind(cls, name),
    }
    undo = None
    try:
        undo = mech_fn(cls, name, value)
        row["patch_error"] = None
    except Exception as e:  # noqa: BLE001
        row["patch_error"] = f"{type(e).__name__}: {str(e)[:160]}"
    row["during"] = {
        "inst": effective_default(cls, name),
        "field": field_default(cls, name),
        "dict": class_dict_kind(cls, name),
    }
    if undo is not None:
        try:
            undo()
            row["undo_error"] = None
        except Exception as e:  # noqa: BLE001
            row["undo_error"] = f"{type(e).__name__}: {str(e)[:160]}"
    row["after"] = {
        "inst": effective_default(cls, name),
        "field": field_default(cls, name),
        "dict": class_dict_kind(cls, name),
    }
    # verdict
    leaked = row["after"]["inst"] != row["before"]["inst"] or row["after"]["field"] != row["before"]["field"]
    row["leaked"] = bool(leaked)
    row["patch_visible_to_instances"] = row["during"]["inst"] == value
    row["clean"] = (not row["patch_error"]) and (not row.get("undo_error")) and not leaked
    return row


def control_group():
    """Methods, handlers, computed vars, ClassVars, classmethods: claimed fine."""
    rows = []

    class S(rx.State):
        base: int = 1
        CV: ClassVar[int] = 10

        def helper(self):
            return "orig"

        @rx.event
        def bump(self):
            self.base += 1

        @rx.var
        def doubled(self) -> int:
            return self.base * 2

        @classmethod
        def cm(cls):
            return "cm-orig"

    def attempt(label, target, name, value, check):
        row = {"control": label}
        for mech_label, mech_fn in (
            ("monkeypatch.setattr", m_monkeypatch),
            ("mock.patch.object", m_mock_patch_object),
        ):
            sub = {}
            try:
                undo = mech_fn(target, name, value)
                sub["patch_error"] = None
            except Exception as e:  # noqa: BLE001
                sub["patch_error"] = f"{type(e).__name__}: {str(e)[:120]}"
                undo = None
            try:
                sub["during"] = check()
            except Exception as e:  # noqa: BLE001
                sub["during"] = f"<{type(e).__name__}: {str(e)[:80]}>"
            if undo is not None:
                try:
                    undo()
                    sub["undo_error"] = None
                except Exception as e:  # noqa: BLE001
                    sub["undo_error"] = f"{type(e).__name__}: {str(e)[:120]}"
            try:
                sub["after"] = check()
            except Exception as e:  # noqa: BLE001
                sub["after"] = f"<{type(e).__name__}: {str(e)[:80]}>"
            row[mech_label] = sub
        rows.append(row)

    attempt("method helper", S, "helper", lambda self: "patched", lambda: inst(S).helper())
    attempt("classmethod cm", S, "cm", classmethod(lambda cls: "cm-patched"), lambda: S.cm())
    attempt("ClassVar CV", S, "CV", 11, lambda: S.CV)
    attempt(
        "computed var doubled",
        S,
        "doubled",
        property(lambda self: 12345),
        lambda: getattr(inst(S), "doubled", "?"),
    )
    attempt("event handler bump (replace with plain func)", S, "bump", lambda self: None, lambda: callable(S.bump) and "callable")
    return rows


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else None
    rows = []
    for kl, kf in KINDS.items():
        for ml, mf in MECHS.items():
            rows.append(run_one(kl, kf, ml, mf))
    ctl = control_group()
    result = {"reflex": REFLEX_VERSION, "venv": EXPECT, "matrix": rows, "control": ctl}
    if out:
        with open(out, "w") as fh:
            json.dump(result, fh, indent=1, default=repr)
    # human table
    print(f"reflex {REFLEX_VERSION}   (venv {EXPECT})")
    cur = None
    for r in rows:
        if r["kind"] != cur:
            cur = r["kind"]
            print(f"\n== {cur}")
        if "setup_error" in r:
            print(f"   {r['mech']:<56} SETUP ERROR {r['setup_error']}")
            continue
        flags = []
        if r["patch_error"]:
            flags.append("PATCH-ERR " + r["patch_error"][:70])
        if r.get("undo_error"):
            flags.append("UNDO-ERR " + r["undo_error"][:70])
        if r["leaked"]:
            flags.append(f"LEAK inst {r['before']['inst']!r}->{r['after']['inst']!r} field {r['before']['field']!r}->{r['after']['field']!r}")
        vis = "visible" if r["patch_visible_to_instances"] else "invisible"
        status = "CLEAN" if r["clean"] else "BROKEN"
        print(f"   {r['mech']:<56} {status:<6} patch {vis:<9} {'; '.join(flags)}")
    print("\n== control group (claimed fine)")
    for c in ctl:
        for k in ("monkeypatch.setattr", "mock.patch.object"):
            s = c[k]
            print(f"   {c['control']:<46} {k:<20} patch_err={s['patch_error']} during={s['during']!r} undo_err={s['undo_error']} after={s['after']!r}")


if __name__ == "__main__":
    main()
