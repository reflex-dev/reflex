"""#7516 regression hunt, Python level: framework paths that set class attributes named like state vars.
Run: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_internals.py
Every row prints `ROW <name> | <result>`; compare a4 vs a3 vs 0.9.12.
"""
import os
import pickle
import sys
import traceback
from typing import ClassVar

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

VER = version("reflex")
print(f"reflex {VER} python {sys.version.split()[0]}")
N = [0]


def row(name, fn):
    try:
        r = fn()
    except Exception as e:  # noqa: BLE001
        tb = traceback.extract_tb(e.__traceback__)[-1]
        r = f"EXC {type(e).__name__}: {str(e)[:150]} @ {os.path.basename(tb.filename)}:{tb.lineno}"
    print(f"ROW {name} | {r}")


def uniq(p):
    N[0] += 1
    return f"{p}{N[0]}"


def inst(cls):
    return cls(_reflex_internal_init=True)


def fields(cls):
    return getattr(cls, "__fields__", None) or cls.get_fields()


# 1. parent var named like the child's auto setter
def setter_collision():
    P = type(uniq("P"), (rx.State,), {"__module__": __name__, "__annotations__": {"set_color": str}, "set_color": "p"})
    C = type(uniq("C"), (P,), {"__module__": __name__, "__annotations__": {"color": str}, "color": "c"})
    return f"created; C.set_color is {type(C.__dict__.get('set_color', P.__dict__.get('set_color'))).__name__}; setvar={type(C.setvar).__name__}"


row("parent var 'set_color' + child var 'color' (auto setter name collides)", setter_collision)


# 2. add_var on parent / child / after substates exist
def add_var_cases():
    P = type(uniq("P"), (rx.State,), {"__module__": __name__, "__annotations__": {"a": int}, "a": 1})
    C = type(uniq("C"), (P,), {"__module__": __name__, "__annotations__": {"b": int}, "b": 2})
    P.add_var("dyn", int, 7)
    C.add_var("dyn2", str, "x")
    out = [f"P.dyn={inst(P).dyn}", f"C.dyn={inst(C).dyn}", f"C.dyn2={inst(C).dyn2}"]
    try:
        C.add_var("dyn", int, 9)
        out.append("C.add_var(dyn) accepted")
    except NameError as e:
        out.append(f"C.add_var(dyn) NameError")
    try:
        P.dyn = 5
        out.append("P.dyn=5 accepted")
    except TypeError:
        out.append("P.dyn=5 TypeError")
    fields(P)["dyn"].default = 8
    out.append(f"field default 8 -> {inst(P).dyn}")
    return " ".join(out)


row("add_var parent/child + field default on a dynamic var", add_var_cases)


# 3. ComponentState created many times with per-component __fields__ defaults (docs pattern), default_factory and named storage
class Editable(rx.ComponentState):
    text: str = "init"
    items: list[str] = []
    theme: str = rx.LocalStorage("light", name="theme")

    @classmethod
    def get_component(cls, initial_value=None, key=None, **props):
        if initial_value is not None:
            fields(cls)["text"].default = initial_value
            fields(cls)["items"].default_factory = lambda v=initial_value: [v]
        if key is not None:
            fields(cls)["theme"].default = rx.LocalStorage("dark", name=f"theme_{key}")
        return rx.text(cls.text, **props)


def cs_many():
    from reflex.compiler.utils import _compile_client_storage_recursive

    comps = [Editable.create(initial_value=f"v{i}", key=f"k{i}") for i in range(50)]
    plain = Editable.create()
    vals = [inst(c.State).text for c in comps]
    items = [list(inst(c.State).items) for c in comps]
    ok = vals == [f"v{i}" for i in range(50)] and items == [[f"v{i}"] for i in range(50)]
    tmpl = fields(Editable)["text"].default, fields(Editable)["theme"].default.name
    keys = set()
    for c in comps + [plain]:
        for d in _compile_client_storage_recursive(c.State):
            for k, v in d.items():
                if "theme" in k:
                    keys.add(v.get("name"))
    s = inst(comps[3].State)
    s.text = "changed"
    s.reset()
    return (f"50 instances own defaults={ok}; plain instance text={inst(plain.State).text!r} items={list(inst(plain.State).items)}; "
            f"template field untouched={tmpl == ('init', 'theme')}; storage keys={len(keys)} (want 51: theme + 50 per-key) "
            f"sample={sorted(keys)[:3]}; reset->{s.text!r}")


row("ComponentState.create x50 with cls.__fields__ defaults/factory/storage key", cs_many)


def cs_assign_in_get_component():
    class Bad(rx.ComponentState):
        text: str = "x"

        @classmethod
        def get_component(cls, initial_value="y", **props):
            cls.text = initial_value  # a3 docs pattern
            return rx.text(cls.text)

    Bad.create()
    return "accepted"


row("ComponentState get_component doing `cls.text = initial` (a3 docs pattern)", cs_assign_in_get_component)


def cs_template_get_component_direct():
    class T(rx.ComponentState):
        text: str = "x"

        @classmethod
        def get_component(cls, initial_value="y", **props):
            fields(cls)["text"].default = initial_value
            return rx.text(cls.text)

    a = T.create(initial_value="A")
    T.get_component(initial_value="TEMPLATE")  # misuse: called on the template class
    b = T.create()
    return f"after T.get_component on the template: template default={fields(T)['text'].default!r}; a={inst(a.State).text!r} b={inst(b.State).text!r}"


row("ComponentState: get_component called directly on the template", cs_template_get_component_direct)


# 4. mixins: change a default on a mixin before/after concrete states are created
def mixin_default():
    M = type(uniq("M"), (rx.State,), {"__module__": __name__, "__annotations__": {"m": int}, "m": 1}, mixin=True)
    A = type(uniq("A"), (M, rx.State), {"__module__": __name__})
    fields(M)["m"].default = 5
    B = type(uniq("B"), (M, rx.State), {"__module__": __name__})
    r = []
    for cls, nm in ((M, "M.m=2"), (A, "A.m=2")):
        try:
            setattr(cls, "m", 2)
            r.append(f"{nm} accepted")
        except TypeError:
            r.append(f"{nm} TypeError")
    return f"A (before)={inst(A).m} B (after)={inst(B).m}; A owns copy={fields(A)['m'] is not fields(M)['m']}; {' '.join(r)}"


row("mixin field default before/after concrete states (docs: only later states)", mixin_default)


# 5. ClassVar redeclaring an inherited var on a substate; new names; delete + re-set
def classvar_cases():
    P = type(uniq("P"), (rx.State,), {"__module__": __name__, "__annotations__": {"x": int, "CFG": ClassVar[int]}, "x": 1, "CFG": 1})
    C = type(uniq("C"), (P,), {"__module__": __name__, "__annotations__": {"x": ClassVar[int]}, "x": 5})
    out = []
    for label, fn in (("C.x=6 (ClassVar over inherited var)", lambda: setattr(C, "x", 6)),
                      ("P.x=2 (var)", lambda: setattr(P, "x", 2)),
                      ("P.CFG=9", lambda: setattr(P, "CFG", 9)),
                      ("C.CFG=10", lambda: setattr(C, "CFG", 10)),
                      ("P.brand_new=1", lambda: setattr(P, "brand_new", 1)),
                      ("C.brand_new=2", lambda: setattr(C, "brand_new", 2))):
        try:
            fn()
            out.append(f"{label}: ok")
        except TypeError:
            out.append(f"{label}: TypeError")
    return f"{'; '.join(out)} | C.x={C.x} P.CFG={P.CFG} C.CFG={C.CFG} 'x' in C.__fields__={'x' in fields(C)} inst(C).x={getattr(inst(C), 'x', '?')}"


row("ClassVar / new names", classvar_cases)


def del_reset_cases():
    P = type(uniq("P"), (rx.State,), {"__module__": __name__, "__annotations__": {"x": int, "_b": int}, "x": 1, "_b": 2})
    C = type(uniq("C"), (P,), {"__module__": __name__, "__annotations__": {"y": int}, "y": 3})
    out = []
    try:
        del C.x
        out.append("del C.x (inherited): accepted")
    except TypeError as e:
        out.append(f"del C.x (inherited): TypeError '{str(e)[:60]}'")
    del P._b
    P._b = 99
    out.append(f"del P._b; P._b=99 -> P._b={P._b!r} inst={getattr(inst(P), '_b', '?')!r}")
    return "; ".join(out)


row("delete inherited via substate / delete+re-set on declaring class", del_reset_cases)


# 6. rx.Model / dataclass vars; pickle and reset with a field-configured default
class Item(rx.Model, table=True):
    name: str = ""


def model_var():
    S = type(uniq("S"), (rx.State,), {"__module__": __name__, "__annotations__": {"rows": list[Item], "one": Item}, "rows": [], "one": Item(name="d")})
    fields(S)["rows"].default_factory = lambda: [Item(name="cfg")]
    s = inst(S)
    s.rows.append(Item(name="x"))
    s2 = pickle.loads(pickle.dumps(s))
    s.reset()
    try:
        S.rows = []
        a = "S.rows=[] accepted"
    except TypeError:
        a = "S.rows=[] TypeError"
    return f"rows after reset={[r.name for r in s.rows]} pickled={[r.name for r in s2.rows]} one={s.one.name}; {a}"


row("rx.Model vars + default_factory + pickle + reset", model_var)


# 7. setvar / auto setters with field-configured defaults
def setters():
    S = type(uniq("S"), (rx.State,), {"__module__": __name__, "__annotations__": {"v": int}, "v": 0})
    fields(S)["v"].default = 4
    s = inst(S)
    has_set = "set_v" in S.event_handlers
    S.event_handlers["setvar"].fn(s, "v", 9)
    return f"default 4 -> {inst(S).v}; setvar -> {s.v}; auto setter set_v present={has_set}"


row("setvar / auto setters", setters)


# 8. rx._x.client_state
def client_state():
    cs = rx._x.client_state(default=3, var_name="cs_x")
    return f"client_state ok: {type(cs).__name__}"


row("rx._x.client_state", client_state)


# 9. SharedState subclass + field default
def shared():
    SS = type(uniq("SS"), (rx.SharedState,), {"__module__": __name__, "__annotations__": {"count": int}, "count": 0})
    fields(SS)["count"].default = 3
    try:
        SS.count = 1
        a = "SS.count=1 accepted"
    except TypeError:
        a = "SS.count=1 TypeError"
    return f"SharedState field default -> {inst(SS).count}; {a}; links default={fields(rx.State)['_reflex_internal_links'].default!r}"


row("rx.SharedState subclass", shared)


# 10. dynamic route arg var
def dyn_route():
    app = rx.App()
    S = type(uniq("R"), (rx.State,), {"__module__": __name__, "__annotations__": {"other": int}, "other": 0})

    def page():
        return rx.text(rx.State.slug)

    app.add_page(page, route="/post/[slug]")
    return f"route arg var on State: {'slug' in rx.State.computed_vars} type={type(rx.State.__dict__.get('slug')).__name__}"


row("dynamic route /post/[slug]", dyn_route)
