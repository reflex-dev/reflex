"""#7519 copy-at-definition regression hunt (Part 1 a, b, d, e).

Run: EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_copydef.py
Every row prints `ROW <id> <name> | <result>`; diff the outputs of 0.9.12 / a4 / a5.
"""
import asyncio
import copy
import dataclasses
import io
import os
import pickle
import sys
import threading
import traceback
from typing import Any, ClassVar

import reflex as rx

assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__
from importlib.metadata import version  # noqa: E402

VER = version("reflex")
print(f"reflex {VER} python {sys.version.split()[0]}")
N = [0]


def uniq(p):
    N[0] += 1
    return f"{p}{N[0]}"


def exc(e):
    tb = traceback.extract_tb(e.__traceback__)
    last = tb[-1]
    user = [f for f in tb if f.filename.endswith("probe_copydef.py")]
    u = f" (user frame line {user[-1].lineno})" if user else ""
    return f"{type(e).__name__}: {str(e)[:160]} @ {os.path.basename(last.filename)}:{last.lineno}{u}"


def row(rid, name, fn):
    try:
        r = fn()
    except Exception as e:  # noqa: BLE001
        r = "EXC " + exc(e)
    print(f"ROW {rid} {name} | {r}", flush=True)


def inst(cls):
    return cls(_reflex_internal_init=True)


def mk(name_prefix, ann: dict, vals: dict, base=None, **kw):
    """Define a state class through a class statement equivalent (type())."""
    ns = {"__module__": __name__, "__annotations__": dict(ann), **vals}
    return type(uniq(name_prefix), (base or rx.State,), ns, **kw)


def staged(ann, vals, attr, base=None, after=None):
    """Report where a default fails: classdef / init / access / pickle / ok."""
    try:
        C = mk("Stg", ann, vals, base)
    except Exception as e:  # noqa: BLE001
        return "FAIL@classdef " + exc(e)
    if after:
        after(C)
    try:
        s = inst(C)
    except Exception as e:  # noqa: BLE001
        return "FAIL@init " + exc(e)
    try:
        v = getattr(s, attr)
    except Exception as e:  # noqa: BLE001
        return "FAIL@access " + exc(e)
    try:
        pickle.dumps(s)
        p = "pickle ok"
    except Exception as e:  # noqa: BLE001
        p = "pickle FAIL " + type(e).__name__
    return f"ok type={type(v).__name__} same_obj_as_declared={v is vals.get(attr)}; {p}"


# ---------- (a) defaults populated AFTER the class statement
def a1():
    OPTIONS: list[str] = []
    C = mk("A1", {"options": list[str]}, {"options": OPTIONS})
    OPTIONS.append("late")
    return f"new instance options={inst(C).options!r} default_value()={C.__fields__['options'].default_value() if hasattr(C,'__fields__') else C.get_fields()['options'].default}"


def a2():
    REG: dict[str, str] = {}
    C = mk("A2", {"_handlers": dict[str, str]}, {"_handlers": REG})

    def register(fn):
        REG[fn.__name__] = fn.__name__
        return fn

    @register
    def plugin_a(): ...

    return f"backend registry seen by new instance={inst(C)._handlers!r}"


def a3():
    LATE: list[str] = []
    C = mk("A3", {"plugins": list[str]}, {"plugins": rx.field(LATE)})
    LATE.append("late")
    return f"rx.field(LATE) new instance={inst(C).plugins!r}"


def a4_():
    LATE: list[str] = []
    C = mk("A4", {"plugins": list[str]}, {"plugins": rx.field(default_factory=lambda: LATE)})
    LATE.append("late")
    s = inst(C)
    return f"rx.field(default_factory=lambda: LATE) new instance={s.plugins!r} is LATE={s.plugins is LATE}"


def a5():
    CONFIG: dict[str, Any] = {}
    C = mk("A5", {"_config": dict[str, Any]}, {"_config": CONFIG})
    s_before = inst(C)
    CONFIG.update({"api": "https://x", "retries": 3})  # e.g. loaded in app lifespan/startup
    s_after = inst(C)
    s_before.reset()
    return f"lazy config: instance created before load={s_before._config!r} (after reset), after load={s_after._config!r}"


def a6():
    P_OPTS: list[str] = ["p"]
    P = mk("A6P", {"opts": list[str]}, {"opts": P_OPTS})
    C_OPTS: list[str] = ["c"]
    C = mk("A6C", {}, {"opts": C_OPTS}, base=P)  # unannotated override of an inherited var
    P_OPTS.append("late")
    C_OPTS.append("late")
    return f"parent={inst(P).opts!r} child-override={C.__fields__['opts'].default_value()!r}"


def a7():
    T = (["x"],)  # tuple holding a list: is_immutable(tuple) -> no copy at all
    C = mk("A7", {"t": tuple}, {"t": T})
    s1, s2 = inst(C), inst(C)
    s1.t[0].append("leak")
    return f"tuple-of-list default: s1.t is s2.t={s1.t is s2.t} s2.t={s2.t!r} T={T!r}"


def a8():
    OPTIONS: list[str] = []
    C = mk("A8", {"options": list[str]}, {"options": OPTIONS})
    OPTIONS.append("late")
    # what the UI builds from the class (docs: rx.foreach(State._x.default_value(), ...))
    return f"UI-time default_value after late append={C.__fields__['options'].default_value()!r}"


def a9():
    OPTIONS: list[str] = []
    C = mk("A9", {}, {"options": OPTIONS})  # unannotated public list
    OPTIONS.append("late")
    return f"unannotated public list default -> {inst(C).options!r}"


def a10():
    # the module-level pattern: populate after class, then app = rx.App(); class read by a page function
    OPTIONS: list[str] = []
    C = mk("A10", {"_choices": list[str]}, {"_choices": OPTIONS})
    for name in ("red", "green"):
        OPTIONS.append(name)
    s = inst(C)
    return f"backend _choices={s._choices!r}"


for rid, name, fn in [
    ("a1", "module list appended after class (frontend var)", a1),
    ("a2", "dict filled by a decorator after class (backend var)", a2),
    ("a3", "rx.field(LATE) appended after class", a3),
    ("a4", "rx.field(default_factory=lambda: LATE)", a4_),
    ("a5", "lazily loaded config dict (backend), instance before/after + reset", a5),
    ("a6", "inherited var overridden by unannotated subclass value, both appended later", a6),
    ("a7", "tuple holding a list (nested mutability)", a7),
    ("a8", "field.default_value() at UI build after late append", a8),
    ("a9", "unannotated public list appended after", a9),
    ("a10", "backend list populated by a loop after class", a10),
]:
    row(rid, name, fn)


# ---------- (b) defaults that cannot be deep-copied
class Holder:
    def __init__(self):
        self.lock = threading.Lock()
        self.n = 1


def fh():
    return open(__file__)  # noqa: SIM115


try:
    import httpx

    CLIENT = httpx.AsyncClient
except ImportError:
    CLIENT = None

cases_b = [
    ("b1", "backend `_lock: Any = threading.Lock()`", {"_lock": Any}, {"_lock": threading.Lock()}, "_lock"),
    ("b2", "backend `_h: Holder = Holder()` (object holding a Lock)", {"_h": Holder}, {"_h": Holder()}, "_h"),
    ("b3", "frontend `h: Any = Holder()`", {"h": Any}, {"h": Holder()}, "h"),
    ("b4", "backend `_fh: Any = open(__file__)`", {"_fh": Any}, {"_fh": fh()}, "_fh"),
    ("b5", "backend `_client: Any = httpx.AsyncClient()`", {"_client": Any}, {"_client": CLIENT() if CLIENT else None}, "_client"),
    ("b6", "backend `_alock: asyncio.Lock = asyncio.Lock()`", {"_alock": asyncio.Lock}, {"_alock": asyncio.Lock()}, "_alock"),
    ("b7", "unannotated public `lock = threading.Lock()`", {}, {"lock": threading.Lock()}, "lock"),
    ("b8", "ClassVar control `_lock: ClassVar[Any] = threading.Lock()`", {"_lock": ClassVar[Any]}, {"_lock": threading.Lock()}, "_lock"),
    ("b9", "backend `_h: Any = rx.field(Holder())`", {"_h": Any}, {"_h": rx.field(Holder())}, "_h"),
    ("b10", "frontend `h: Holder = Holder()`", {"h": Holder}, {"h": Holder()}, "h"),
    ("b11", "unannotated private `_lock = threading.Lock()` (plain attr control)", {}, {"_lock": threading.Lock()}, "_lock"),
    ("b12", "backend `_ev: Any = threading.Event()`", {"_ev": Any}, {"_ev": threading.Event()}, "_ev"),
]
for rid, name, ann, vals, attr in cases_b:
    row(rid, name, lambda ann=ann, vals=vals, attr=attr: staged(ann, vals, attr))


def b_setdefault():
    C = mk("BSD", {"_h": Any}, {"_h": None})
    f = C.__fields__["_h"]
    if not hasattr(f, "set_default"):
        f.default = Holder()
        return "no set_default; .default=Holder() accepted, instance _h is shared=" + str(inst(C)._h is f.default)
    try:
        f.set_default(Holder())
    except Exception as e:  # noqa: BLE001
        return "set_default(Holder()) FAIL " + exc(e)
    return "set_default(Holder()) ok"


row("b13", "set_default(Holder()) on a backend var", b_setdefault)


def b_setdefault_factory():
    C = mk("BSF", {"_h": Any}, {"_h": None})
    f = C.__fields__["_h"]
    if not hasattr(f, "set_default"):
        return "no set_default"
    H = Holder()
    f.set_default(default_factory=lambda: H)
    s1, s2 = inst(C), inst(C)
    return f"set_default(default_factory=lambda: H): shared-by-identity={s1._h is s2._h is H}"


row("b14", "set_default(default_factory=lambda: H) (documented escape hatch?)", b_setdefault_factory)


# ---------- (d) identity-shared defaults
class Registry:
    def __init__(self):
        self.items = []


REGISTRY = Registry()
SENTINEL = object()


def d1():
    C = mk("D1", {"_reg": Registry}, {"_reg": REGISTRY})
    s = inst(C)
    return f"backend `_reg = REGISTRY`: instance._reg is REGISTRY={s._reg is REGISTRY}"


def d2():
    C = mk("D2", {"_mark": Any}, {"_mark": SENTINEL})
    s = inst(C)
    return f"backend `_mark = SENTINEL(object())`: is SENTINEL={s._mark is SENTINEL}"


def d3():
    C = mk("D3", {"_reg": ClassVar[Registry]}, {"_reg": REGISTRY})
    s = inst(C)
    return f"ClassVar control: is REGISTRY={s._reg is REGISTRY}"


def d4():
    C = mk("D4", {"_reg": Registry}, {"_reg": REGISTRY})
    s1, s2 = inst(C), inst(C)
    return f"two instances share _reg={s1._reg is s2._reg}"


for rid, name, fn in [("d1", "identity default backend", d1), ("d2", "sentinel object()", d2), ("d3", "ClassVar identity", d3), ("d4", "two instances share", d4)]:
    row(rid, name, fn)


# ---------- (e) shapes: isolation, reset, pickle
@dataclasses.dataclass
class DC:
    tags: list[str] = dataclasses.field(default_factory=lambda: ["t"])
    n: int = 0


try:
    import pydantic

    class PM(pydantic.BaseModel):
        tags: list[str] = ["p"]
        n: int = 0
except ImportError:
    PM = None


def iso(C, attr, mutate, fmt=repr):
    s1, s2 = inst(C), inst(C)
    mutate(getattr(s1, attr))
    a = fmt(getattr(s2, attr))
    d = fmt(C.__fields__[attr].default_value())
    mutate(getattr(s1, attr))
    s1.reset()
    r = fmt(getattr(s1, attr))
    try:
        p = fmt(getattr(pickle.loads(pickle.dumps(s1)), attr))
    except Exception as e:  # noqa: BLE001
        p = "FAIL " + type(e).__name__
    return f"s2 after s1 mutation={a} default_value()={d} s1 after reset={r} pickled={p}"


def e_rows():
    yield "e1", "rx.field(default=[...])", mk("E1", {"x": list[str]}, {"x": rx.field(["a"])}), "x", lambda v: v.append("m")
    yield "e2", "rx.field(default_factory=list)", mk("E2", {"x": list[str]}, {"x": rx.field(default_factory=lambda: ["a"])}), "x", lambda v: v.append("m")
    yield "e3", "rx.Field[list[str]] = rx.field([...])", mk("E3", {"x": rx.Field[list[str]]}, {"x": rx.field(["a"])}), "x", lambda v: v.append("m")
    yield "e4", "class body list", mk("E4", {"x": list[str]}, {"x": ["a"]}), "x", lambda v: v.append("m")
    yield "e5", "dict of lists", mk("E5", {"x": dict[str, list[int]]}, {"x": {"k": [1]}}), "x", lambda v: v["k"].append(2)
    yield "e6", "dataclass object default", mk("E6", {"x": DC}, {"x": DC()}), "x", lambda v: v.tags.append("m")
    if PM:
        yield "e7", "pydantic model default", mk("E7", {"x": PM}, {"x": PM()}), "x", lambda v: v.tags.append("m")
    yield "e8", "backend set", mk("E8", {"_x": set}, {"_x": {1}}), "_x", lambda v: v.add(2)
    yield "e9", "backend nested dict", mk("E9", {"_x": dict}, {"_x": {"a": {"b": []}}}), "_x", lambda v: v["a"]["b"].append(1)


for rid, name, C, attr, mutate in e_rows():
    row(rid, name, lambda C=C, attr=attr, mutate=mutate: iso(C, attr, mutate))


def e10():
    try:
        Base = rx.Base
    except Exception as e:  # noqa: BLE001
        return "rx.Base unavailable: " + exc(e)

    class BM(Base):
        tags: list[str] = ["b"]

    C = mk("E10", {"x": BM}, {"x": BM()})
    return iso(C, "x", lambda v: v.tags.append("m"))


row("e10", "rx.Base model default", e10)


def e11():
    class Mix(rx.State, mixin=True):
        mx: list[str] = ["m"]

    U1 = mk("E11U", {}, {}, base=Mix)
    U2 = mk("E11V", {}, {}, base=Mix)
    s1, s2 = inst(U1), inst(U2)
    s1.mx.append("x")
    t1 = inst(U1)
    return f"mixin list: U2 instance={s2.mx!r} fresh U1={t1.mx!r} U1 field is U2 field={U1.__fields__['mx'] is U2.__fields__['mx']}"


row("e11", "mixin mutable default isolation", e11)


def e12():
    P = mk("E12P", {"items": list[str]}, {"items": ["p"]})
    C = mk("E12C", {"c": int}, {"c": 0}, base=P)
    root = inst(P)
    return f"substate inherits field: C.__fields__['items'] is P's={C.__fields__['items'] is P.__fields__['items']} P default={P.__fields__['items'].default_value()!r} instance={root.items!r}"


row("e12", "substate inheriting a mutable default", e12)


class CS(rx.ComponentState):
    items: list[str] = ["base"]
    _seen: dict = {}

    @classmethod
    def get_component(cls, tag: str = "", **props):
        if tag:
            if hasattr(cls.__fields__["items"], "set_default"):
                cls.__fields__["items"].set_default(["base", tag])
            else:
                cls.__fields__["items"].default_factory = lambda: ["base", tag]
        return rx.text(cls.items.to_string())


def e13():
    comps = [CS.create(tag=f"t{i}") for i in range(60)]
    states = [c.State for c in comps]
    vals = [inst(S).items for S in states[:3]] + [inst(states[-1]).items]
    template = CS.__fields__["items"].default_value()
    distinct = len({id(S.__fields__["items"]) for S in states})
    s = inst(states[5])
    s.items.append("x")
    s.reset()
    return f"60 ComponentStates: first/last defaults={vals} template={template!r} distinct fields={distinct} reset={s.items!r}"


row("e13", "ComponentState.create x60 with set_default per component", e13)


def e14():
    # a ComponentState class-body mutable default appended after definition
    LATE: list[str] = []

    class CS2(rx.ComponentState):
        items: list[str] = LATE

        @classmethod
        def get_component(cls, **props):
            return rx.text(cls.items.to_string())

    LATE.append("late")
    c = CS2.create()
    return f"ComponentState created after late append sees={inst(c.State).items!r}"


row("e14", "ComponentState class default appended after definition, create() after", e14)
