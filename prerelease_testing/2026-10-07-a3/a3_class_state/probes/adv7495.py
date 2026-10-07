"""Adversarial probes for reflex#7495 (class-level default assignment: storage kept, patch/restore undo stack,
rejected assignments, __delattr__) and #7494 (pickle contents), run identically on 0.9.12 / 0.10.0a2 / 0.10.0a3.

Run from a neutral dir:  REFLEX_TELEMETRY_ENABLED=false EXPECT_VENV=<venv> <venv>/bin/python -I adv7495.py [case-substring...]
Needs pytest in the venv (MonkeyPatch). Each case builds its own classes, prints `CASE <name> | <facts>` and never
aborts the run. Compare the per-version outputs with diff.
"""

import copy
import importlib
import os
import pickle
import sys
import tempfile
import textwrap
import threading
import traceback
from typing import Any, Optional
from unittest import mock

import pytest
import reflex as rx

EXPECT = os.environ["EXPECT_VENV"]
assert f"/envs/{EXPECT}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

VER = version("reflex")
print(f"reflex {VER} reflex-base {version('reflex-base')} python {sys.version.split()[0]} venv {EXPECT}")

try:
    from reflex.compiler.utils import _compile_client_storage_recursive
except ImportError:  # pragma: no cover
    _compile_client_storage_recursive = None

WANT = sys.argv[1:]
N = [0]


def uniq(prefix):
    N[0] += 1
    return f"{prefix}{N[0]}"


def inst(cls):
    try:
        return cls(_reflex_internal_init=True)
    except TypeError:
        return cls()


def short(v, n=70):
    v = getattr(v, "__wrapped__", v)
    if isinstance(v, (int, float, str, bool, type(None), list, dict, tuple)):
        r = repr(v)
    else:
        r = f"<{type(v).__name__}:{str(v)[:40]}>"
    return r[:n]


def iv(cls, name):
    """What a brand new instance reads."""
    try:
        return short(getattr(inst(cls), name))
    except Exception as e:  # noqa: BLE001
        return f"<EXC {type(e).__name__}: {str(e)[:60]}>"


def fd(cls, name):
    """The registered field default (default_value())."""
    try:
        f = cls.get_fields()[name]
    except Exception as e:  # noqa: BLE001
        return f"<no field: {type(e).__name__}>"
    try:
        return short(f.default_value())
    except Exception as e:  # noqa: BLE001
        return f"<EXC {type(e).__name__}>"


def depth(cls, name):
    try:
        f = cls.get_fields()[name]
    except Exception:  # noqa: BLE001
        return "-"
    d = getattr(f, "__dict__", {}).get("_replaced_defaults")
    return "-" if d is None else len(d)


def exc(fn):
    try:
        r = fn()
        return "ok" if r is None else f"ok:{short(r)}"
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {str(e)[:90]}"


def storage_entry(cls, name):
    if _compile_client_storage_recursive is None:
        return "n/a"
    try:
        ck, ls, ss = _compile_client_storage_recursive(cls)
    except Exception as e:  # noqa: BLE001
        return f"<compile EXC {type(e).__name__}: {str(e)[:60]}>"
    for kind, d in (("cookie", ck), ("local", ls), ("session", ss)):
        for k, v in d.items():
            if k.rsplit(".", 1)[-1].split("_rx_state_")[0] == name:
                return {"kind": kind, **v}
    return None


def is_cs(cls, name):
    try:
        return cls._is_client_storage(name)
    except Exception as e:  # noqa: BLE001
        return f"<EXC {type(e).__name__}>"


CASES = []


def case(fn):
    CASES.append(fn)
    return fn


def mkstate(prefix="S", base=None, **ns):
    """Create a module-level-like state class with annotations from a dict of name -> (annotation, default)."""
    ann = {k: v[0] for k, v in ns.items()}
    body = {k: v[1] for k, v in ns.items() if v[1] is not ...}
    body["__annotations__"] = ann
    body["__module__"] = __name__
    return type(uniq(prefix), (base or rx.State,), body)


# 1-6: delete / self-assign / manual save-restore
@case
def del_unassigned_frontend():
    S = mkstate(count=(int, 0))
    r = exc(lambda: delattr(S, "count"))
    after = type(S.__dict__.get("count")).__name__
    s = inst(S)
    w = exc(lambda: setattr(s, "count", 3))
    return (f"del={r} | class-dict entry after={after} | 'count' in get_fields={'count' in S.get_fields()} | "
            f"S.count is Var={isinstance(getattr(S, 'count', None), rx.Var)} | fresh={iv(S, 'count')} | inst write={w} -> {short(getattr(s, 'count', '<none>'))}")


@case
def del_unassigned_backend():
    S = mkstate(_b=(int, 1))
    r = exc(lambda: delattr(S, "_b"))
    after = type(S.__dict__.get("_b")).__name__
    return f"del={r} | class-dict entry after={after} | fresh={iv(S, '_b')} | field default={fd(S, '_b')}"


@case
def del_twice_after_one_assignment():
    S = mkstate(count=(int, 0))
    a = exc(lambda: setattr(S, "count", 10))
    f1 = iv(S, "count")
    d1 = exc(lambda: delattr(S, "count"))
    f2 = iv(S, "count")
    d2 = exc(lambda: delattr(S, "count"))
    f3 = iv(S, "count")
    return f"assign10={a} fresh={f1} | del#1={d1} fresh={f2} | del#2={d2} fresh={f3} (depth {depth(S, 'count')})"


@case
def self_assign_after_config():
    S = mkstate(count=(int, 0), _b=(int, 0))
    S.count = 10
    S._b = 10
    a = exc(lambda: setattr(S, "count", S.count))
    b = exc(lambda: setattr(S, "_b", S._b))
    return f"S.count=10; S.count=S.count -> {a}, fresh={iv(S, 'count')} | S._b=10; S._b=S._b -> {b}, fresh={iv(S, '_b')}"


@case
def self_assign_no_config():
    S = mkstate(count=(int, 0), _b=(int, 0))
    a = exc(lambda: setattr(S, "count", S.count))
    b = exc(lambda: setattr(S, "_b", S._b))
    return f"S.count=S.count -> {a}, fresh={iv(S, 'count')} | S._b=S._b -> {b}, fresh={iv(S, '_b')}"


@case
def manual_save_restore_getattr():
    S = mkstate(count=(int, 0), _b=(int, 0))
    old, oldb = S.count, S._b
    S.count = 10
    S._b = 10
    a = exc(lambda: setattr(S, "count", old))
    b = exc(lambda: setattr(S, "_b", oldb))
    return f"restore count -> {a}, fresh={iv(S, 'count')} | restore _b -> {b}, fresh={iv(S, '_b')}"


# 7-8: more than 16 assignments
@case
def over16_assign_then_restore():
    S = mkstate(count=(int, 0))
    saved = S.__dict__["count"]
    for i in range(1, 21):
        S.count = i
    seq = []
    for _ in range(21):
        try:
            setattr(S, "count", saved)
        except Exception as e:  # noqa: BLE001
            seq.append(f"EXC {type(e).__name__}")
            break
        seq.append(iv(S, "count"))
    return f"20 assignments 1..20, then 21 restores -> {seq} (orig 0)"


@case
def over16_nested_monkeypatch():
    S = mkstate(count=(int, 0))
    mps = []
    errs = []
    for i in range(1, 21):
        mp = pytest.MonkeyPatch()
        try:
            mp.setattr(S, "count", i)
        except Exception as e:  # noqa: BLE001
            errs.append(f"set{i}:{type(e).__name__}")
        mps.append(mp)
    during = iv(S, "count")
    for mp in reversed(mps):
        try:
            mp.undo()
        except Exception as e:  # noqa: BLE001
            errs.append(f"undo:{type(e).__name__}")
    return f"20 nested monkeypatches: during={during} after LIFO undo={iv(S, 'count')} (orig 0) errors={errs[:3]}"


@case
def config_then_17_patch_roundtrips():
    S = mkstate(count=(int, 0))
    S.count = 10
    errs = []
    for i in range(17):
        mp = pytest.MonkeyPatch()
        try:
            mp.setattr(S, "count", 100 + i)
            mp.undo()
        except Exception as e:  # noqa: BLE001
            errs.append(type(e).__name__)
    return f"config 10, 17 sequential patch round trips -> fresh={iv(S, 'count')} depth={depth(S, 'count')} errors={errs[:2]}"


# 9-13: rejected assignments followed by a restore
def _rejected(value_fn, label):
    S = mkstate(count=(int, 0))
    Other = mkstate("O", y=(int, 1))
    S.count = 10  # configured default (e.g. module-level config)
    mp = pytest.MonkeyPatch()
    r = exc(lambda: mp.setattr(S, "count", value_fn(Other)))
    during = iv(S, "count")
    u = exc(mp.undo)
    return f"config 10; monkeypatch.setattr(S,'count',{label}) -> {r} | during={during} | undo={u} | after={iv(S, 'count')} (want 10)"


@case
def rejected_wrong_type_then_undo():
    return _rejected(lambda O: "bad", "'bad'")


@case
def rejected_var_then_undo():
    return _rejected(lambda O: O.y, "Other.y (a Var)")


@case
def rejected_field_then_undo():
    return _rejected(lambda O: rx.field(5), "rx.field(5)")


@case
def rejected_raising_factory_then_undo():
    return _rejected(lambda O: (lambda: 1 / 0), "lambda: 1/0")


@case
def rejected_var_then_undo_mock():
    S = mkstate(count=(int, 0))
    Other = mkstate("O", y=(int, 1))
    S.count = 10
    r = "no error"
    try:
        with mock.patch.object(S, "count", Other.y):
            pass
    except Exception as e:  # noqa: BLE001
        r = f"{type(e).__name__}: {str(e)[:60]}"
    return f"config 10; with mock.patch.object(S,'count',Other.y) -> {r} | after={iv(S, 'count')} (want 10)"


@case
def rejected_wrong_type_then_undo_mock():
    S = mkstate(count=(int, 0))
    S.count = 10
    r = "no error"
    try:
        with mock.patch.object(S, "count", "bad"):
            pass
    except Exception as e:  # noqa: BLE001
        r = f"{type(e).__name__}: {str(e)[:60]}"
    return f"config 10; with mock.patch.object(S,'count','bad') -> {r} | after={iv(S, 'count')} (want 10)"


@case
def rejected_in_user_code_no_restore():
    S = mkstate(count=(int, 0))
    r = exc(lambda: setattr(S, "count", "bad"))
    d0 = depth(S, "count")
    mp = pytest.MonkeyPatch()
    p = exc(lambda: mp.setattr(S, "count", 5))
    u = exc(mp.undo)
    a = iv(S, "count")
    d = exc(lambda: delattr(S, "count"))
    return f"S.count='bad' -> {r} (depth now {d0}) | later patch 5 -> {p} + undo -> {u} -> {a} | stray del -> {d}, fresh={iv(S, 'count')}"


@case
def declared_factory_raises_on_plain_assign():
    flag = {"boom": False, "calls": 0}

    def fac():
        flag["calls"] += 1
        if flag["boom"]:
            raise RuntimeError("factory needs app context")
        return "d"

    S = mkstate(v=(str, rx.field(default_factory=fac)))
    c0 = flag["calls"]
    S.v = lambda: "cfg"  # configured factory
    c1 = flag["calls"]
    flag["boom"] = True
    r1 = exc(lambda: setattr(S, "v", "plain"))
    after_plain = iv(S, "v")
    S2 = mkstate(v=(str, rx.field(default_factory=fac)))
    flag["boom"] = True
    S2.__dict__  # noqa: B018
    r2 = exc(lambda: setattr(S2, "v", "x"))
    return (f"declared factory calls: at class creation={c0}, by assigning a factory={c1 - c0} | S.v='plain' after configuring a factory -> {r1}, fresh={after_plain} | "
            f"fresh class, raising declared factory, S2.v='x' -> {r2}")


@case
def declared_factory_raising_assign_then_mp_undo_with_config():
    flag = {"boom": False}

    def cfg():
        if flag["boom"]:
            raise RuntimeError("cfg factory fails later")
        return "cfg"

    S = mkstate(v=(str, "d"))
    S.v = cfg  # configured default factory
    flag["boom"] = True
    mp = pytest.MonkeyPatch()
    r = exc(lambda: mp.setattr(S, "v", "patched"))
    u = exc(mp.undo)
    f = S.get_fields()["v"]
    return (f"config factory; it later raises; monkeypatch.setattr(S,'v','patched') -> {r} | undo -> {u} | "
            f"field now default={short(f.default)} factory={getattr(f.default_factory, '__name__', f.default_factory)} (want factory=cfg)")


# 14-18: parent / child / mixin / shadowing
@case
def parent_patch_via_child_monkeypatch():
    P = mkstate("P", x=(int, 1))
    C = mkstate("C", base=P)
    mp = pytest.MonkeyPatch()
    r = exc(lambda: mp.setattr(C, "x", 9))
    during = (iv(P, "x"), iv(C, "x"))
    u = exc(mp.undo)
    return f"patch via child -> {r}; during P,C={during}; undo -> {u}; after P={iv(P, 'x')} C={iv(C, 'x')} ; C.x still Var={isinstance(C.x, rx.Var)}"


@case
def parent_patch_via_child_mock():
    P = mkstate("P", x=(int, 1), _y=(int, 1))
    C = mkstate("C", base=P)
    r = "ok"
    try:
        with mock.patch.object(C, "x", 9), mock.patch.object(C, "_y", 9):
            during = (iv(P, "x"), iv(C, "x"), iv(C, "_y"))
    except Exception as e:  # noqa: BLE001
        r = f"{type(e).__name__}: {str(e)[:70]}"
        during = None
    return f"mock via child -> {r}; during={during}; after P.x={iv(P, 'x')} C.x={iv(C, 'x')} C._y={iv(C, '_y')} P._y={iv(P, '_y')}"


@case
def grandchild_patch():
    P = mkstate("P", x=(int, 1))
    C = mkstate("C", base=P)
    G = mkstate("G", base=C)
    mp = pytest.MonkeyPatch()
    r = exc(lambda: mp.setattr(G, "x", 9))
    during = (iv(P, "x"), iv(C, "x"), iv(G, "x"))
    u = exc(mp.undo)
    return f"patch via grandchild -> {r}; during P,C,G={during}; undo -> {u}; after={iv(P, 'x'), iv(C, 'x'), iv(G, 'x')}"


@case
def mixin_patch():
    Mx = type(uniq("Mx"), (rx.State,), {"__annotations__": {"m": int, "_mb": int}, "m": 1, "_mb": 1, "__module__": __name__}, mixin=True)
    U = type(uniq("U"), (Mx, rx.State), {"__module__": __name__})
    mp = pytest.MonkeyPatch()
    r = exc(lambda: mp.setattr(Mx, "m", 7))
    U2 = type(uniq("U"), (Mx, rx.State), {"__module__": __name__})
    u = exc(mp.undo)
    U3 = type(uniq("U"), (Mx, rx.State), {"__module__": __name__})
    mp2 = pytest.MonkeyPatch()
    r2 = exc(lambda: mp2.setattr(U, "_mb", 9))
    d2 = iv(U, "_mb")
    u2 = exc(mp2.undo)
    return (f"patch mixin -> {r}; undo -> {u}; U(before)={iv(U, 'm')} U2(during)={iv(U2, 'm')} U3(after)={iv(U3, 'm')} | "
            f"patch U._mb -> {r2} during={d2} undo -> {u2} after={iv(U, '_mb')} mixin _mb={fd(Mx, '_mb')}")


@case
def shadowing_child_var():
    P = mkstate("P", x=(int, 1))
    try:
        C = mkstate("C", base=P, x=(int, 2))
    except Exception as e:  # noqa: BLE001
        return f"cannot declare shadowing var: {type(e).__name__}: {str(e)[:60]}"
    mp = pytest.MonkeyPatch()
    r = exc(lambda: mp.setattr(C, "x", 9))
    during = (iv(P, "x"), iv(C, "x"))
    u = exc(mp.undo)
    return f"patch shadowing child -> {r}; during P,C={during}; undo -> {u}; after P={iv(P, 'x')} C={iv(C, 'x')}"


# 19-20: ComponentState and reset()
@case
def componentstate_per_instance_defaults_and_patch():
    class Ctr(rx.ComponentState):
        count: int = 0
        _hidden: int = 0

        @classmethod
        def get_component(cls, *children, start=0, **props):
            cls.count = start
            cls._hidden = start * 100
            return rx.text(cls.count)

    comps = [Ctr.create(start=s) for s in (10, 20, 30)]
    vals = [(iv(c.State, "count"), iv(c.State, "_hidden")) for c in comps]
    st = inst(comps[1].State)
    st.count = 5
    st.reset()
    reset1 = (st.count, st._hidden)
    mp = pytest.MonkeyPatch()
    r = exc(lambda: mp.setattr(comps[1].State, "count", 99))
    during = iv(comps[1].State, "count")
    u = exc(mp.undo)
    st2 = inst(comps[1].State)
    st2.count = 7
    st2.reset()
    return (f"3 instances count/_hidden={vals} | template Ctr.count field={fd(Ctr, 'count')} | reset->{reset1} | "
            f"patch inst2 -> {r} during={during} undo -> {u} | reset after restore -> {st2.count} (want 20)")


@case
def reset_after_assignment_and_after_restore():
    S = mkstate(count=(int, 0), _b=(list[int], [1]))
    S.count = 10
    S._b = [7]
    s = inst(S)
    s.count = 3
    s._b.append(8)
    s.reset()
    r1 = (s.count, list(s._b))
    d = exc(lambda: delattr(S, "count"))
    d2 = exc(lambda: delattr(S, "_b"))
    s.count = 4
    s.reset()
    r2 = (s.count, list(s._b))
    return f"after assign: reset -> {r1} (want (10,[7])) | del -> {d},{d2} | reset -> {r2} (want (0,[1])) | fresh={iv(S, 'count')},{iv(S, '_b')}"


# 21-24, 31-32: storage
def _storage_declared_factory_calls(ann):
    calls = {"n": 0}

    def fac():
        calls["n"] += 1
        return rx.LocalStorage("d", name="dfk")

    S = mkstate(v=(ann, rx.field(default_factory=fac)))
    c = [("class", calls["n"])]
    S._is_client_storage("v")
    c.append(("is_client_storage", calls["n"]))
    e0 = storage_entry(S, "v")
    c.append(("compile", calls["n"]))
    inst(S).v  # noqa: B018
    inst(S).v  # noqa: B018
    c.append(("2 instances", calls["n"]))
    r = exc(lambda: setattr(S, "v", "x"))
    c.append(("assign 'x'", calls["n"]))
    inst(S).v  # noqa: B018
    e1 = storage_entry(S, "v")
    c.append(("inst+compile", calls["n"]))
    return f"cumulative factory calls {c} | before={e0} | assign -> {r} | after={e1} | fresh={iv(S, 'v')} is_cs={is_cs(S, 'v')}"


@case
def storage_declared_factory_calls_str_ann():
    return "(#7498 known: str annotation) " + _storage_declared_factory_calls(str)


@case
def storage_declared_factory_calls_storage_ann():
    return _storage_declared_factory_calls(rx.LocalStorage)


@case
def storage_assigned_factory_calls():
    calls = {"n": 0}

    def fac():
        calls["n"] += 1
        return rx.LocalStorage("x", name="afk")

    S = mkstate(v=(str, rx.LocalStorage("d", name="k")))
    r = exc(lambda: setattr(S, "v", fac))
    c1 = calls["n"]
    inst(S).v  # noqa: B018
    inst(S).v  # noqa: B018
    e = storage_entry(S, "v")
    return f"S.v = fac -> {r} | calls at assignment={c1} after 2 instances+compile={calls['n']} | entry={e} fresh={iv(S, 'v')}"


@case
def storage_plain_returning_factory_on_storage_factory_decl():
    calls = {"d": 0, "a": 0}

    def dfac():
        calls["d"] += 1
        return rx.Cookie("d", name="ck_df", max_age=60)

    def afac():
        calls["a"] += 1
        return "plain"

    S = mkstate(v=(str, rx.field(default_factory=dfac)))
    r = exc(lambda: setattr(S, "v", afac))
    c = dict(calls)
    inst(S).v  # noqa: B018
    return f"declared storage factory + assigned plain factory -> {r} | calls at assign={c} after inst={calls} | entry={storage_entry(S, 'v')} fresh={iv(S, 'v')}"


@case
def storage_optional_none():
    S = mkstate(v=(Optional[str], rx.LocalStorage("d", name="kopt")))
    before = (is_cs(S, "v"), storage_entry(S, "v"))
    r = exc(lambda: setattr(S, "v", None))
    mid = (is_cs(S, "v"), storage_entry(S, "v"), iv(S, "v"))
    r2 = exc(lambda: setattr(S, "v", "x"))
    after = (is_cs(S, "v"), storage_entry(S, "v"), iv(S, "v"))
    return f"v: Optional[str] = LocalStorage('d', name='kopt'): before={before} | S.v=None -> {r} {mid} | then S.v='x' -> {r2} {after}"


@case
def storage_union_annotation_nonstr():
    from typing import Union

    S = mkstate(v=(Union[str, int], rx.LocalStorage("d", name="kany")))
    before = (is_cs(S, "v"), storage_entry(S, "v"))
    r = exc(lambda: setattr(S, "v", 5))
    mid = (is_cs(S, "v"), storage_entry(S, "v"), iv(S, "v"))
    return f"v: Union[str,int] = LocalStorage(name='kany'): before={before} | S.v=5 -> {r} {mid}"


@case
def storage_options_kept():
    out = []
    for label, decl in (
        ("Cookie(max_age,path,same_site,secure)", rx.Cookie("d", name="ckopt", max_age=3600, path="/p", same_site="strict", secure=True)),
        ("LocalStorage(sync=True)", rx.LocalStorage("d", name="lsopt", sync=True)),
        ("SessionStorage(name)", rx.SessionStorage("d", name="ssopt")),
    ):
        S = mkstate(v=(str, decl))
        before = storage_entry(S, "v")
        r = exc(lambda: setattr(S, "v", "x"))
        after = storage_entry(S, "v")
        out.append(f"{label}: assign -> {r}; same entry={before == after}; after={after}; fresh={iv(S, 'v')}; type={type(S.get_fields()['v'].default).__name__}")
    return " || ".join(out)


@case
def storage_restore_after_plain_assign():
    S = mkstate(v=(str, rx.LocalStorage("d", name="krest")))
    mp = pytest.MonkeyPatch()
    r = exc(lambda: mp.setattr(S, "v", "patched"))
    during = (is_cs(S, "v"), storage_entry(S, "v"), iv(S, "v"))
    u = exc(mp.undo)
    f = S.get_fields()["v"].default
    return f"patch LocalStorage var 'patched' -> {r} during={during} | undo -> {u} | after default={f!r} type={type(f).__name__} name={getattr(f, 'name', None)} is_cs={is_cs(S, 'v')}"


@case
def storage_cs_multi_instances_same_key():
    class Box(rx.ComponentState):
        pref: str = rx.LocalStorage("light", name="box_pref")
        nameless: str = rx.LocalStorage("n0")

        @classmethod
        def get_component(cls, *children, initial="light", **props):
            cls.pref = initial
            cls.nameless = f"n-{initial}"
            return rx.text(cls.pref)

    out = []
    for ini in ("dark", "blue", "red"):
        c = Box.create(initial=ini)
        out.append((iv(c.State, "pref"), storage_entry(c.State, "pref"), storage_entry(c.State, "nameless")))
    return f"3 ComponentState instances (fresh pref, entry pref, entry nameless): {out}"


# 25: pickling with an undo stack
def importable_state(src_body, clsname):
    """Write a state class into a temp module so instances pickle like an app's states."""
    d = tempfile.mkdtemp(prefix="adv7495p_")
    mod = uniq("pk_")
    open(os.path.join(d, f"{mod}.py"), "w").write("import reflex as rx\n" + textwrap.dedent(src_body))
    sys.path.insert(0, d)
    try:
        return getattr(importlib.import_module(mod), clsname)
    finally:
        sys.path.remove(d)


@case
def pickle_with_undo_stack():
    S = importable_state("""
        class PkState(rx.State):
            count: int = 0
            _b: int = 0
            label: str = "x"
    """, "PkState")
    try:
        sch0 = S._to_schema()
    except Exception as e:  # noqa: BLE001
        sch0 = f"<{type(e).__name__}>"
    S.count = 10
    S._b = 11
    s = inst(S)
    data = pickle.dumps(s)
    try:
        ser = s._serialize()
    except Exception as e:  # noqa: BLE001
        ser = f"<{type(e).__name__}: {e}>".encode()
    sch1 = S._to_schema() if hasattr(S, "_to_schema") else "-"
    keys = sorted(s.__getstate__()) if hasattr(s, "__getstate__") else "-"
    fpk = exc(lambda: len(pickle.dumps(S.get_fields()["count"])))
    fdc = exc(lambda: type(copy.deepcopy(S.get_fields()["count"])).__name__)
    loaded = pickle.loads(data)
    try:
        cls_loaded = S._deserialize(ser)
        rt = (cls_loaded.count, cls_loaded._b)
    except Exception as e:  # noqa: BLE001
        rt = f"<{type(e).__name__}>"
    return (f"__getstate__ keys={keys} | b'_replaced_defaults' in pickle={b'_replaced_defaults' in data} in _serialize={b'_replaced_defaults' in ser} | "
            f"dirty_vars/_backend_vars in _serialize={b'dirty_vars' in ser}/{b'_backend_vars' in ser} | schema unchanged by assignment={sch0 == sch1} | "
            f"pickle Field={fpk} deepcopy Field={fdc} | loads count/_b={loaded.count},{loaded._b} | _deserialize={rt}")


# 26-28: non-LIFO and interleaved restores
@case
def patch_then_runtime_assign_then_undo():
    S = mkstate(count=(int, 0))
    mp = pytest.MonkeyPatch()
    mp.setattr(S, "count", 99)
    a = exc(lambda: setattr(S, "count", 77))  # e.g. code under test assigns a class default
    u = exc(mp.undo)
    return f"patch 99; code assigns 77; undo -> {u} | after={iv(S, 'count')} (plain-attribute semantics: 0)"


@case
def monkeypatch_delattr_with_config():
    S = mkstate(count=(int, 0))
    S.count = 10
    mp = pytest.MonkeyPatch()
    r = exc(lambda: mp.delattr(S, "count"))
    during = iv(S, "count")
    u = exc(mp.undo)
    return f"config 10; monkeypatch.delattr -> {r}, during={during} | undo -> {u}, after={iv(S, 'count')} (want 10)"


@case
def non_lifo_mock_start_stop():
    S = mkstate(count=(int, 0))
    p1 = mock.patch.object(S, "count", 1)
    p2 = mock.patch.object(S, "count", 2)
    seq = []
    for step, f in (("p1.start", p1.start), ("p2.start", p2.start), ("p1.stop", p1.stop), ("p2.stop", p2.stop)):
        r = exc(f)
        seq.append(f"{step}:{r if r != 'ok' and not r.startswith('ok:') else ''}{iv(S, 'count')}")
    return " -> ".join(seq) + " (plain-attribute semantics end at 1)"


# 29: thread stress
@case
def thread_stress_assign_restore():
    S = mkstate(count=(int, 0), _f=(str, "d"))
    saved, savedf = S.__dict__["count"], S.__dict__["_f"]
    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    errs = []

    def worker(i):
        for j in range(1500):
            try:
                setattr(S, "count", i * 10000 + j)
                setattr(S, "count", saved)
                setattr(S, "_f", (lambda v=f"{i}-{j}": v))
                setattr(S, "_f", savedf)
            except Exception as e:  # noqa: BLE001
                errs.append(f"{type(e).__name__}: {str(e)[:50]}")

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    sys.setswitchinterval(old)
    f = S.get_fields()["_f"]
    return (f"8 threads x 1500 (assign, restore) -> errors={len(errs)} {errs[:2]} | count={iv(S, 'count')} (want 0) | "
            f"_f={iv(S, '_f')} default={short(f.default)} factory={f.default_factory} (want 'd', None) depth={depth(S, 'count')}")


# 30: AppHarness-style reuse across apps / module reloads
@case
def module_reload_reuse():
    d = tempfile.mkdtemp(prefix="adv7495_")
    tag = uniq("m")
    open(os.path.join(d, f"st_{tag}.py"), "w").write(textwrap.dedent(f"""
        import reflex as rx
        class Shared{tag}(rx.State):
            count: int = 0
    """))
    open(os.path.join(d, f"app_{tag}.py"), "w").write(textwrap.dedent(f"""
        from st_{tag} import Shared{tag}
        Shared{tag}.count = 10
    """))
    sys.path.insert(0, d)
    try:
        st = importlib.import_module(f"st_{tag}")
        app = importlib.import_module(f"app_{tag}")
        cls = getattr(st, f"Shared{tag}")
        for _ in range(20):
            importlib.reload(app)
        a = iv(cls, "count")
        mp = pytest.MonkeyPatch()
        p = exc(lambda: mp.setattr(cls, "count", 99))
        u = exc(mp.undo)
        b = f"{p}/{u}/{iv(cls, 'count')}"
        dl = [exc(lambda: delattr(cls, "count")) for _ in range(3)]
        c = iv(cls, "count")
    finally:
        sys.path.remove(d)
    return f"app module reloaded 20x (each assigns 10): fresh={a} depth={depth(cls, 'count')} | patch+undo -> {b} | 3 dels -> {dl} fresh={c}"


@case
def classification_cache_after_restore():
    S = mkstate(plain=(str, "p"))
    c0 = is_cs(S, "plain")
    mp = pytest.MonkeyPatch()
    r = exc(lambda: mp.setattr(S, "plain", rx.LocalStorage("x", name="kc")))
    c1 = (is_cs(S, "plain"), storage_entry(S, "plain"))
    u = exc(mp.undo)
    S2 = mkstate(plain=(str, "p"))
    mp2 = pytest.MonkeyPatch()
    r2 = exc(lambda: mp2.setattr(S2, "plain", rx.LocalStorage("x", name="kc2")))
    u2 = exc(mp2.undo)
    return (f"plain var, is_cs before={c0}; patch with LocalStorage -> {r} during={c1}; undo -> {u}; after: default={short(S.get_fields()['plain'].default)} "
            f"is_cs={is_cs(S, 'plain')} entry={storage_entry(S, 'plain')} | same without a lookup during the patch: is_cs after={is_cs(S2, 'plain')} entry={storage_entry(S2, 'plain')}")


# 33: ClassVar / non-field attributes unaffected by __delattr__/__setattr__
@case
def non_field_attrs_delete_and_set():
    from typing import ClassVar

    S = type(uniq("S"), (rx.State,), {"__annotations__": {"CV": ClassVar[int], "count": int}, "CV": 1, "count": 0, "__module__": __name__,
                                      "helper": lambda self: 1})
    r1 = exc(lambda: setattr(S, "CV", 2))
    v1 = S.CV
    r2 = exc(lambda: delattr(S, "CV"))
    r3 = exc(lambda: delattr(S, "helper"))
    r4 = exc(lambda: delattr(S, "nonexistent"))
    return f"ClassVar set -> {r1} ({v1}); del ClassVar -> {r2} hasattr={hasattr(S, 'CV')}; del method -> {r3} hasattr={hasattr(S, 'helper')}; del missing -> {r4}"


if __name__ == "__main__":
    for fn in CASES:
        if WANT and not any(w in fn.__name__ for w in WANT):
            continue
        try:
            res = fn()
        except Exception as e:  # noqa: BLE001
            res = f"CASE CRASHED {type(e).__name__}: {str(e)[:120]} @ {traceback.extract_tb(e.__traceback__)[-1].lineno}"
        print(f"CASE {fn.__name__} | {res}")
