"""Issue 1 verifier: State.add_var on a substate for a name a parent already got via add_var.

Run from this dir (never from the checkout):
  EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_addvar.py
Every row prints `ROW <name> | <result>`; compare a4 / a3 / 0.9.12.
"""
import os
import pickle
import sys
import traceback
from unittest import mock

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

from reflex.compiler.utils import compile_state  # noqa: E402

print(f"reflex {version('reflex')} python {sys.version.split()[0]}")
N = [0]


def row(name, fn):
    try:
        r = fn()
    except Exception as e:  # noqa: BLE001
        tb = traceback.extract_tb(e.__traceback__)[-1]
        r = f"EXC {type(e).__name__}: {str(e)[:170]} @ {os.path.basename(tb.filename)}:{tb.lineno}"
    print(f"ROW {name} | {r}", flush=True)


def uniq(p):
    N[0] += 1
    return f"{p}{N[0]}"


def mk(name, bases, ann=None, **ns):
    n = uniq(name)
    cls = type(n, bases, {"__module__": __name__, "__annotations__": dict(ann or {}), **ns})
    globals()[n] = cls  # picklable by qualified name
    return cls


def fields(cls):
    return getattr(cls, "__fields__", None) or cls.get_fields()


def js(v):
    return getattr(v, "_js_expr", type(v).__name__)


def tree(P):
    p = P(_reflex_internal_init=True)
    return p, p.substates


def attempt(fn):
    try:
        fn()
        return "ok"
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {str(e)[:110]}"


# A. the reported case: C defined BEFORE P.add_var, D defined AFTER.
P = mk("P", (rx.State,), {"a": int}, a=1)
C = mk("C", (P,), {"b": int}, b=2)
P.add_var("dyn", int, 7)
D = mk("D", (P,), {"d": int}, d=3)

row("A1 after P.add_var: 'dyn' in C.__fields__ / C.vars / D.__fields__ / D.vars",
    lambda: f"{'dyn' in fields(C)} / {'dyn' in C.vars} / {'dyn' in fields(D)} / {'dyn' in D.vars}; "
            f"C.dyn js={js(C.dyn)} D.dyn js={js(D.dyn)} C.vars[dyn] js={js(C.vars['dyn'])}")


def tree_read():
    p, subs = tree(P)
    c = subs[C.get_name()]
    d = subs[D.get_name()]
    return f"p.dyn={p.dyn} c.dyn={c.dyn} d.dyn={d.dyn}"


row("A2 tree read before C.add_var", tree_read)
row("A3 C.add_var('dyn', int, 9)", lambda: (C.add_var("dyn", int, 9), "accepted")[1])


def after():
    f = fields(C).get("dyn")
    pf = fields(P)["dyn"]
    return (f"C.__fields__ has dyn={f is not None} same-as-P's={f is pf} owner={getattr(f, '_owner', '?')!r} "
            f"default={getattr(f, 'default', '?')!r}; C.vars[dyn] js={js(C.vars.get('dyn'))}; "
            f"C.dyn js={js(C.dyn)}; 'dyn' in C.base_vars={'dyn' in C.base_vars}; 'dyn' in C.__dict__={'dyn' in C.__dict__}")


row("A4 C after the add_var attempt", after)


def tree_after():
    p, subs = tree(P)
    c = subs[C.get_name()]
    out = [f"p.dyn={p.dyn} c.dyn={c.dyn}"]
    c.dyn = 3
    out.append(f"after c.dyn=3: p.dyn={p.dyn} c.dyn={c.dyn} p.dirty={sorted(p.dirty_vars)} c.dirty={sorted(c.dirty_vars)}")
    d = p.dict()
    out.append(f"dict P.dyn={d[P.get_full_name()].get('dyn_rx_state_', d[P.get_full_name()].get('dyn'))} "
               f"C keys={sorted(d[C.get_full_name()])}")
    c2 = pickle.loads(pickle.dumps(c))
    out.append(f"pickle(c) vars={sorted(k for k in vars(c2) if not k.startswith('_') and k not in ('parent_state','substates','dirty_vars','dirty_substates'))}")
    p2 = pickle.loads(pickle.dumps(p))
    out.append(f"pickle(p) dyn={vars(p2).get('dyn')}")
    c.reset()
    p.reset()
    out.append(f"reset -> p.dyn={p.dyn} c.dyn={c.dyn}")
    return "; ".join(out)


row("A5 tree after (read/write/dict/pickle/reset)", tree_after)


def compiled():
    st = compile_state(P)
    return f"P.dyn={st[P.get_full_name()].get('dyn_rx_state_', st[P.get_full_name()].get('dyn'))} C keys={sorted(st[C.get_full_name()])}"


row("A6 compile_state(P) (initial frontend state)", compiled)
row("A7 schema C._to_schema()", lambda: C._to_schema() if hasattr(C, "_to_schema") else "n/a")
row("A8 retry C.add_var('dyn', int, 9)", lambda: attempt(lambda: C.add_var("dyn", int, 9)))


def follow_message():
    if not isinstance(fields(C).get("dyn"), object) or "dyn" not in fields(C):
        return "n/a (no C.__fields__['dyn'])"
    fields(C)["dyn"].default = 11
    p, subs = tree(P)
    return f"after C.__fields__['dyn'].default=11: p.dyn={p.dyn} c.dyn={subs[C.get_name()].dyn} (P field default={fields(P)['dyn'].default!r})"


row("A9 follow the error message: C.__fields__['dyn'].default = 11", follow_message)
row("A10 D (defined after P.add_var).add_var('dyn', int, 9)", lambda: attempt(lambda: D.add_var("dyn", int, 9)))
row("A11 C.add_var('dyn2') (new name) still works", lambda: attempt(lambda: C.add_var("dyn2", str, "x")))
row("A12 P.add_var('dyn') again -> NameError expected", lambda: attempt(lambda: P.add_var("dyn", int, 7)))


# B. the guard does not see inherited dynamic vars on substates (no add_var on the substate).
def bypass():
    P2 = mk("P", (rx.State,), {"a": int}, a=1)
    E = mk("E", (P2,), {"e": int}, e=2)
    P2.add_var("dyn", int, 7)
    F = mk("F", (P2,), {"f": int}, f=3)
    out = [f"static inherited: E.a=5 -> {attempt(lambda: setattr(E, 'a', 5))}"]
    out.append(f"P2.dyn=5 (declaring) -> {attempt(lambda: setattr(P2, 'dyn', 5))}")
    out.append(f"E.dyn=5 (before) -> {attempt(lambda: setattr(E, 'dyn', 5))}")
    out.append(f"F.dyn=5 (after) -> {attempt(lambda: setattr(F, 'dyn', 5))}")
    out.append(f"E.dyn now {E.dyn!r}")
    p, subs = tree(P2)
    out.append(f"tree: p.dyn={p.dyn} e.dyn={subs[E.get_name()].dyn!r}")
    G = mk("G", (P2,), {"g": int}, g=3)
    with mock.patch.object(G, "dyn", 42):
        inside = G.dyn
    out.append(f"mock.patch.object(G,'dyn',42) inside={inside!r} after={js(G.dyn)}")
    return "; ".join(out)


row("B1 class assignment of an INHERITED add_var var through a substate", bypass)


# C. static shadowing on each version (what "shadow" means when declared in the class body)
def static_shadow():
    P3 = mk("P", (rx.State,), {"a": int}, a=1)
    out = []
    for label, ann, ns in (("annotated a: int = 5", {"a": int}, {"a": 5}), ("unannotated a = 5", {}, {"a": 5})):
        try:
            K = mk("K", (P3,), ann, **ns)
            p, subs = tree(P3)
            k = subs[K.get_name()]
            k.a = 6
            out.append(f"{label}: created, own={'a' in K.__dict__} K.a js={js(K.a)} p.a={p.a} k.a={k.a}")
        except Exception as e:  # noqa: BLE001
            out.append(f"{label}: {type(e).__name__}: {str(e)[:100]}")
    return "; ".join(out)


row("C1 static redeclaration of a parent var in a substate", static_shadow)


# D. realistic triggers seen in public code
def init_subclass_hook():
    """A base state whose __init_subclass__ gives every subclass a dynamic var (multi-level tree)."""

    class Hooked(rx.State):
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
            cls.add_var("loading", bool, False)

    globals()["Hooked"] = Hooked
    out = []
    try:
        class Page1(Hooked):
            x: int = 0

        globals()["Page1"] = Page1
        out.append("Page1(Hooked) ok")

        class Detail(Page1):
            y: int = 0

        globals()["Detail"] = Detail
        h = Hooked(_reflex_internal_init=True)
        p1 = h.substates[Page1.get_name()]
        d = p1.substates[Detail.get_name()]
        d.loading = True
        out.append(f"Detail(Page1) ok; p1.loading={p1.loading} d.loading={d.loading} Detail.loading js={js(Detail.loading)}")
    except Exception as e:  # noqa: BLE001
        tb = traceback.extract_tb(e.__traceback__)
        out.append(f"{type(e).__name__}: {str(e)[:120]} @ {[f'{os.path.basename(t.filename)}:{t.lineno}' for t in tb[-4:]]}")
    return "; ".join(out)


row("D1 __init_subclass__ hook calling cls.add_var('loading') for every subclass (grandchild)", init_subclass_hook)


def orbitlab_pattern():
    """OrbitLab-OSS/OrbitLab orbitlab/web/utilities.py: class OrbitLabState(CacheBuster, rx.State) where
    CacheBuster.__init_subclass__ does `for var in cls.computed_vars: cls.add_var(f"_cached_{var}", bool, default_value=False)`."""

    class CacheBuster:
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
            for var in cls.computed_vars:
                cls.add_var(f"_cached_{var}", bool, default_value=False)

    out = []
    try:
        class OLState(CacheBuster, rx.State):
            n: int = 0

            @rx.var
            def sectors(self) -> int:
                return self.n

        globals()["OLState"] = OLState

        class SelectOpts(OLState):
            @rx.var
            def options(self) -> int:
                return 1

        globals()["SelectOpts"] = SelectOpts
        out.append(f"parent + substate with its own computed var ok (SelectOpts.computed_vars={sorted(SelectOpts.computed_vars)})")

        class Override(OLState):
            @rx.var
            def sectors(self) -> int:  # 0.10: a substate may redeclare an inherited computed var
                return 2

        globals()["Override"] = Override
        out.append("substate overriding computed var 'sectors' ok")
    except Exception as e:  # noqa: BLE001
        tb = traceback.extract_tb(e.__traceback__)
        out.append(f"{type(e).__name__}: {str(e)[:120]} @ {[f'{os.path.basename(t.filename)}:{t.lineno}' for t in tb[-4:]]}")
    return "; ".join(out)


row("D2 OrbitLab CacheBuster pattern (own computed vars only; then a substate overriding one)", orbitlab_pattern)


def guarded_pattern():
    """iqss-research/debriefly: `if "form_id" not in rx.State.__fields__: rx.State.add_var("form_id", str, "")` --
    the same guard on a substate after its parent got the var."""
    P5 = mk("P", (rx.State,), {"a": int}, a=1)
    C5 = mk("C", (P5,), {"b": int}, b=2)
    out = []
    for S in (P5, C5):
        if "form_id" not in fields(S):
            out.append(f"{S.__name__}.add_var -> {attempt(lambda S=S: S.add_var('form_id', str, ''))}")
        else:
            out.append(f"{S.__name__}: guard skipped")
    return "; ".join(out)


row("D3 `if name not in S.__fields__: S.add_var(name)` guard on parent then substate", guarded_pattern)
