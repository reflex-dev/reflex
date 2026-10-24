"""Python-level checks on the installed reflex for #7500 #7636 #7592 #7410 #7443 #7547 #7606 #7622 #7402 #7401.

Run: cd $W && EXPECT_VENV=<venv> $SB/envs/<venv>/bin/python -I probe_state_misc.py   (add -W error::DeprecationWarning to be strict)
"""

import asyncio
import dataclasses
import gc
import os
import sys
import textwrap
import typing
import warnings
from typing import Any

import pydantic
import reflex as rx

assert f"/envs/{os.environ.get('EXPECT_VENV', 'new')}/" in rx.__file__, rx.__file__
VER = __import__("importlib.metadata").metadata.version("reflex")
print(f"reflex {VER} python {sys.version.split()[0]}")


def row(label, fn):
    try:
        out = fn()
        print(f"OK   {label}: {out}")
    except Exception as e:  # noqa: BLE001
        print(f"EXC  {label}: {type(e).__name__}: {str(e).splitlines()[0][:220]}")


def new(cls):
    return cls(_reflex_internal_init=True)


print("\n== #7500 mutation through dict views / other paths marks the var dirty")


class DState(rx.State):
    d: dict[str, list[int]] = {"a": [1], "b": [2]}
    nd: dict[str, dict[str, int]] = {"x": {"n": 0}}
    lod: list[dict[str, int]] = [{"v": 0}]

    @rx.var(cache=True)
    def total(self) -> int:
        return sum(sum(v) for v in self.d.values())


def mutation_case(label, fn):
    s = new(DState)
    s._clean()
    s.total  # prime the cached var
    try:
        fn(s)
    except Exception as e:  # noqa: BLE001
        print(f"EXC  {label}: {type(e).__name__}: {str(e)[:160]}")
        return
    dirty = sorted(v for v in s.dirty_vars if v in ("d", "nd", "lod"))
    delta = s.get_delta()
    sub = delta.get(s.get_full_name(), {})
    keys = sorted(k.replace("_rx_state_", "") for k in sub)
    print(f"{'DIRTY' if dirty else 'MISSED':6} {label}: dirty={dirty} delta_keys={keys} d={s.d} total_in_delta={sub.get('total_rx_state_')}")


def _c(fn):
    return fn


mutation_case("for v in d.values(): v.append", lambda s: [v.append(1) for v in s.d.values()])
mutation_case("for k, v in d.items(): v.append", lambda s: [v.append(2) for k, v in s.d.items()])
mutation_case("list(d.values())[0].append", lambda s: list(s.d.values())[0].append(3))
mutation_case("d.get('a').append", lambda s: s.d.get("a").append(4))
mutation_case("d.setdefault('z', []).append (new key)", lambda s: s.d.setdefault("z", []).append(5))
mutation_case("d.setdefault('a', []).append (existing key)", lambda s: s.d.setdefault("a", []).append(6))
mutation_case("nd['x']['n'] = 7", lambda s: s.nd["x"].__setitem__("n", 7))
mutation_case("for inner in nd.values(): inner['n'] = 8", lambda s: [inner.__setitem__("n", 8) for inner in s.nd.values()])
mutation_case("for x in lod: x['v'] = 9", lambda s: [x.__setitem__("v", 9) for x in s.lod])
mutation_case("lod[0]['v'] = 10", lambda s: s.lod[0].__setitem__("v", 10))
mutation_case("next(iter(d.values())).append", lambda s: next(iter(s.d.values())).append(11))
mutation_case("reversed(d.values()) first .append", lambda s: next(reversed(s.d.values())).append(14))
mutation_case("[*d.values()][0].append", lambda s: [*s.d.values()][0].append(15))
mutation_case("dict(d)['a'].append (shallow copy)", lambda s: dict(s.d)["a"].append(16))
mutation_case("d.copy()['a'].append", lambda s: s.d.copy()["a"].append(18))
mutation_case("{**d}['a'].append", lambda s: {**s.d}["a"].append(20))
mutation_case("sorted(d.values(), key=len)[0].append", lambda s: sorted(s.d.values(), key=len)[0].append(17))
mutation_case("max(d.values(), key=len).append", lambda s: max(s.d.values(), key=len).append(19))
mutation_case("d.values().mapping['a'].append", lambda s: s.d.values().mapping["a"].append(21))
mutation_case("for v in d.values(): v += [22] (augmented)", lambda s: [v.__iadd__([22]) for v in s.d.values()])
mutation_case("d.items() -> dict(items)['a'].append", lambda s: dict(s.d.items())["a"].append(23))
mutation_case("values() view repr/len/contains only (no mutation)", lambda s: (repr(s.d.values()), len(s.d.values()), [1] in s.d.values()))
mutation_case("v = d.pop('b'); v.append (pop marks dirty)", lambda s: s.d.pop("b").append(12))
mutation_case("d.popitem()[1].append", lambda s: s.d.popitem()[1].append(13))
mutation_case("for v in lod (list) -> v.update", lambda s: [v.update({"w": 1}) for v in s.lod])
mutation_case("v = d['a']; v += [1] (iadd on proxy, no setitem)", lambda s: exec("v = s.d['a']\nv += [1]", {"s": s}))
mutation_case("d['a'] += [1] (setitem path)", lambda s: exec("s.d['a'] += [1]", {"s": s}))
mutation_case("lod += [{}] (iadd on top-level proxy)", lambda s: exec("s.lod += [{'q': 1}]", {"s": s}))


print("\n== #7636 / #7592 rx.Model / pydantic models as handler args and state vars: deprecation warnings")
from reflex_base.event.processor.base_state_processor import _transform_event_payload  # noqa: E402


class Item(rx.Model, table=True):
    name: str = ""
    qty: int = 0


class PydItem(pydantic.BaseModel):
    name: str = ""
    qty: int = 0


try:
    _v1 = pydantic.v1  # removed from pydantic 2.14
except AttributeError:
    print("pydantic.v1 not available in this pydantic:", pydantic.VERSION)
    _v1 = None
if _v1 is not None:

    class V1Item(_v1.BaseModel):
        name: str = ""
        qty: int = 0

else:

    class V1Item(pydantic.BaseModel):  # stand-in so the rest of the probe runs
        name: str = ""
        qty: int = 0


@dataclasses.dataclass
class DCItem:
    name: str = ""
    qty: int = 0


with warnings.catch_warnings(record=True) as w_def:
    warnings.simplefilter("always")

    class MState(rx.State):
        item: Item = Item()
        pitem: PydItem = PydItem()
        v1item: V1Item = V1Item()
        dcitem: DCItem = DCItem()
        items: list[Item] = []
        opt_item: Item | None = None

        @rx.event
        def h_model(self, m: Item):
            self.item = m

        @rx.event
        def h_pyd(self, m: PydItem):
            self.pitem = m

        @rx.event
        def h_v1(self, m: V1Item):
            self.v1item = m

        @rx.event
        def h_dc(self, m: DCItem):
            self.dcitem = m

        @rx.event
        def h_list(self, ms: list[Item]):
            self.items = ms

        @rx.event
        def h_opt(self, m: Item | None):
            self.opt_item = m

        @rx.var
        def item_name(self) -> str:
            return self.item.name


print("warnings during MState definition:", [(x.category.__name__, str(x.message)[:90]) for x in w_def])
for hname, payload in [
    ("h_model", {"m": {"name": "a", "qty": 1}}),
    ("h_model", {"m": {"name": "a", "qty": 1, "id": 5, "extra": "ignored?"}}),
    ("h_pyd", {"m": {"name": "b", "qty": 2}}),
    ("h_v1", {"m": {"name": "c", "qty": 3}}),
    ("h_dc", {"m": {"name": "d", "qty": 4}}),
    ("h_list", {"ms": [{"name": "e", "qty": 5}, {"name": "f", "qty": 6}]}),
    ("h_opt", {"m": {"name": "g", "qty": 7}}),
    ("h_opt", {"m": None}),
]:
    handler = getattr(MState, hname)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            hints = typing.get_type_hints(handler.fn)
            out = _transform_event_payload(payload, hints)
            res = {k: f"{type(v).__name__}:{v}" for k, v in out.items()}
        except Exception as e:  # noqa: BLE001
            res = f"EXC {type(e).__name__}: {str(e)[:120]}"
    cats = sorted({x.category.__name__ for x in w})
    print(f"{hname:8} {payload!s:60.60} -> {res!s:70.70} warnings={len(w)} {cats} {[str(x.message)[:70] for x in w][:2]}")
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    s = new(MState)
    s.item = Item(name="z", qty=9)
    s.pitem = PydItem(name="p")
    s.v1item = V1Item(name="v")
    s.items = [Item(name="l")]
    d = s.get_delta()
    _ = s.item_name
    str(MState.item.name), str(MState.pitem.qty), str(MState.v1item.name), str(MState.opt_item.name)
print("warnings for model state vars (assign, get_delta, var access):", len(w), sorted({x.category.__name__ for x in w}), [str(x.message)[:90] for x in w][:3])
print("delta item:", {k: str(v)[:60] for k, v in d.get(s.get_full_name(), {}).items()})


print("\n== #7410 async uncached computed var withheld by a get_delta override (no 'never awaited' warning expected)")
from reflex.istate.delta import resolve_delta  # noqa: E402


class AState(rx.State):
    n: int = 0
    _withhold: bool = False

    @rx.var(cache=False)
    async def av(self) -> int:
        await asyncio.sleep(0)
        return self.n * 10

    @rx.var(cache=False)
    def sv(self) -> int:
        return self.n + 1

    @rx.state._override_base_method
    def get_delta(self):
        delta = super().get_delta()
        sub = delta.get(self.get_full_name(), {})
        if self._withhold:
            sub.pop("av_rx_state_", None)
            sub.pop("sv_rx_state_", None)
        return delta


async def async_filter_case(withhold):
    s = new(AState)
    s._withhold = withhold
    s.n = 1
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        delta = await resolve_delta(s)
        gc.collect()
        await asyncio.sleep(0)
        gc.collect()
    keys = sorted(k.replace("_rx_state_", "") for k in delta.get(s.get_full_name(), {}))
    print(f"withhold={withhold}: delta keys={keys} warnings={[(x.category.__name__, str(x.message)[:80]) for x in w]}")


for wh in (False, True):
    asyncio.run(async_filter_case(wh))


print("\n== #7443 App.modify_state legacy string tokens")


class TState(rx.State):
    v: int = 0


APP = rx.App()


async def modify_cases():
    app = APP
    app._enable_state()
    for label, tok in [
        ("bare client token", "tok1"),
        ("token + unknown path", "tok1_nonexistent___state"),
        ("token + root path", "tok1_" + rx.State.get_full_name()),
        ("token + substate path", "tok1_" + TState.get_full_name()),
        ("token + root path + bogus child", "tok1_" + rx.State.get_full_name() + ".nope"),
        ("empty string", ""),
        ("BaseStateToken", rx.BaseStateToken(ident="tok1", cls=TState)),
    ]:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                async with app.modify_state(tok) as st:
                    res = f"OK -> {type(st).__name__}"
            except Exception as e:  # noqa: BLE001
                res = f"EXC {type(e).__name__}: {str(e)[:150]}"
        print(f"  {label:32} {res}   deprecations={len([x for x in w if 'eprecat' in x.category.__name__])}")
    await app.state_manager.close() if hasattr(app.state_manager, "close") else None


try:
    asyncio.run(modify_cases())
except Exception as e:  # noqa: BLE001
    print("modify_state cases failed to run:", type(e).__name__, e)


print("\n== #7547 undefined names in state var annotations")
SNIPPETS = {
    "future: items: list[Item] = []": "from __future__ import annotations\nimport reflex as rx\nclass S1(rx.State):\n    items: list[Item] = []\n",
    "future: items: list[Item] (no default)": "from __future__ import annotations\nimport reflex as rx\nclass S2(rx.State):\n    items: list[Item]\n",
    "future: backend _items: list[Item] = []": "from __future__ import annotations\nimport reflex as rx\nclass S3(rx.State):\n    _items: list[Item] = []\n",
    "future: rx.Field[Item] = rx.field(None)": "from __future__ import annotations\nimport reflex as rx\nclass S4(rx.State):\n    it: rx.Field[Item | None] = rx.field(None)\n",
    "future: computed var -> Item": "from __future__ import annotations\nimport reflex as rx\nclass S5(rx.State):\n    @rx.var\n    def it(self) -> Item:\n        return None\n",
    "no future: items: list['Item'] = []": "import reflex as rx\nclass S6(rx.State):\n    items: list['Item'] = []\n",
    "no future: items: 'list[Item]' = []": "import reflex as rx\nclass S7(rx.State):\n    items: 'list[Item]' = []\n",
    "no future: items: list[Item] = [] (plain NameError at class body)": "import reflex as rx\nclass S8(rx.State):\n    items: list[Item] = []\n",
    "future: attribute of undefined module: x: mod.Thing = None": "from __future__ import annotations\nimport reflex as rx\nclass S9(rx.State):\n    x: mod.Thing = None\n",
    "future: handler arg annotation undefined": "from __future__ import annotations\nimport reflex as rx\nclass S10(rx.State):\n    @rx.event\n    def h(self, it: Item):\n        pass\n",
}
for label, src in SNIPPETS.items():
    ns = {}
    try:
        exec(textwrap.dedent(src), ns)  # noqa: S102
        print(f"OK   {label} (class created)")
    except Exception as e:  # noqa: BLE001
        print(f"EXC  {label}: {type(e).__name__}: {str(e).splitlines()[0][:150]}")


print("\n== #7606 get_leaf_vars")
try:
    from reflex_base.vars import get_leaf_vars
except ImportError as e:
    print("get_leaf_vars not importable from reflex_base.vars:", e)
    get_leaf_vars = None
if get_leaf_vars:

    class LState(rx.State):
        items: list[str] = []
        d: dict[str, int] = {}
        count: int = 0
        name: str = ""

    def names(vs):
        return [str(v)[-40:] for v in vs]

    row("items[1:]", lambda: names(get_leaf_vars(LState.items[1:])))
    row("items.join(',')", lambda: names(get_leaf_vars(LState.items.join(","))))
    row("count + 1", lambda: names(get_leaf_vars(LState.count + 1)))
    row("literal 3", lambda: names(get_leaf_vars(rx.Var.create(3))))
    row("literal [count, 1]", lambda: names(get_leaf_vars(rx.Var.create([LState.count, 1]))))
    row("d['k']", lambda: names(get_leaf_vars(LState.d["k"])))
    row("count.to(str)", lambda: names(get_leaf_vars(LState.count.to(str))))
    row("items.foreach(lambda x: x.upper())", lambda: names(get_leaf_vars(LState.items.foreach(lambda x: x.upper()))))
    row("items.foreach(lambda x: x + name)", lambda: names(get_leaf_vars(LState.items.foreach(lambda x: x + LState.name))))
    row("cond(count > 1, name, items[0])", lambda: names(get_leaf_vars(rx.cond(LState.count > 1, LState.name, LState.items[0]))))
    row("raw python list", lambda: names(get_leaf_vars(rx.Var.create(["a", "b"]))))
    row("non-var input", lambda: names(get_leaf_vars([LState.count, 1])))


print("\n== #7622 revert: frozenset as array literal")


try:

    class FState(rx.State):
        fs: frozenset[int] = frozenset({1, 2})
        st: set[int] = {1, 2}

    print("OK   state var frozenset[int] accepted")
except Exception as e:  # noqa: BLE001
    print(f"EXC  state var frozenset[int]: {type(e).__name__}: {str(e)[:160]}")

    class FState(rx.State):
        st: set[int] = {1, 2}
        fs: set[int] = {1, 2}


row("Var.create(frozenset({1,2}))", lambda: (type(v := rx.Var.create(frozenset({1, 2}))).__name__, v._var_type, str(v)))
row("Var.create({1,2}) (set)", lambda: (type(v := rx.Var.create({1, 2})).__name__, v._var_type, str(v)))
row("rx.foreach(FState.fs, ...)", lambda: type(rx.foreach(FState.fs, lambda x: rx.text(x))).__name__)
row("rx.foreach(FState.st, ...)", lambda: type(rx.foreach(FState.st, lambda x: rx.text(x))).__name__)
row("FState.fs.length()", lambda: str(FState.fs.length()))
row("FState.fs.contains(1)", lambda: str(FState.fs.contains(1)))
row("rx.text(frozenset) child", lambda: type(rx.box(rx.Var.create(frozenset({"a"})))).__name__)
row("rx.el.div(data_x=frozenset)", lambda: str(rx.el.div(custom_attrs={"data-x": frozenset({1})}).render()["props"])[:80])
row("state delta with frozenset value", lambda: (s := new(FState), setattr(s, "fs", frozenset({3})), str(s.get_delta()))[-1][:120])


print("\n== #7402 / #7401 event sequences and EventCallback binding")
from reflex_base.event import EventHandler, EventSpec, fix_events  # noqa: E402

try:
    from reflex_base.event import event_sequence
except ImportError:
    event_sequence = None
    print("event_sequence not available (expected on 0.10.0)")


class EState(rx.State):
    log: list[str] = []

    @rx.event
    def a(self):
        self.log.append("a")

    @rx.event
    def b(self, x: int = 0):
        self.log.append(f"b{x}")

    @rx.event
    def ret_tuple(self):
        return (EState.a, EState.b(1))

    @rx.event
    def ret_list(self):
        return [EState.a, EState.b(2)]

    @rx.event
    def ret_single(self):
        return EState.a

    @rx.event
    def gen_tuple(self):
        yield (EState.a, EState.b(3))
        yield EState.b(4)


@dataclasses.dataclass
class Holder:
    handler: Any = EState.a
    cb: Any = EState.b(5)


if event_sequence:
    row("event_sequence((a, b))", lambda: [type(e).__name__ for e in event_sequence((EState.a, EState.b(1)))])
    row("event_sequence([a])", lambda: [type(e).__name__ for e in event_sequence([EState.a])])
    row("event_sequence(a)", lambda: [type(e).__name__ for e in event_sequence(EState.a)])
    row("event_sequence(a()) spec", lambda: [type(e).__name__ for e in event_sequence(EState.b(1))])
    row("event_sequence('str')", lambda: event_sequence("str"))
    row("event_sequence(None)", lambda: event_sequence(None))
    row("event_sequence(generator)", lambda: event_sequence(e for e in [EState.a]))
row("rx.button(on_click=(a, b))", lambda: len(rx.button(on_click=(EState.a, EState.b(1))).event_triggers["on_click"].events))
row("rx.button(on_click=[a, b])", lambda: len(rx.button(on_click=[EState.a, EState.b(1)]).event_triggers["on_click"].events))
row("rx.button(on_click=set())", lambda: rx.button(on_click={EState.a}).event_triggers["on_click"])
row("rx.button(on_click=generator)", lambda: len(rx.button(on_click=(e for e in [EState.a])).event_triggers["on_click"].events))
row("rx.button(on_click=lambda: (a, b))", lambda: len(rx.button(on_click=lambda: (EState.a, EState.b(1))).event_triggers["on_click"].events))
row("fix_events(tuple)", lambda: [e.name.split(".")[-1] for e in fix_events((EState.a, EState.b(1)), "tok")])
row("fix_events(handler returning tuple)", lambda: [e.name.split(".")[-1] for e in fix_events(EState.ret_tuple.fn(new(EState)), "tok")])
row("fix_events(single handler)", lambda: [e.name.split(".")[-1] for e in fix_events(EState.a, "tok")])


def run_handler(h):
    s = new(EState)
    out = h.fn(s)
    if hasattr(out, "__next__"):
        out = list(out)
    return str(out)[:160]


row("handler returning tuple -> fix_events", lambda: [e.name.split(".")[-1] for e in fix_events(EState.ret_tuple.fn(new(EState)), "tok")])
row("generator yielding a tuple -> fix_events each", lambda: [[e.name.split(".")[-1] for e in fix_events(y, "tok")] for y in EState.gen_tuple.fn(new(EState))])
app = APP
row("add_page(on_load=(a, b))", lambda: (app.add_page(lambda: rx.text("x"), route="/t1", on_load=(EState.a, EState.b(1))), "ok")[1])
row("add_page(on_load=a)", lambda: (app.add_page(lambda: rx.text("x"), route="/t2", on_load=EState.a), "ok")[1])
row("add_page(on_load=[a, b])", lambda: (app.add_page(lambda: rx.text("x"), route="/t3", on_load=[EState.a, EState.b(1)]), "ok")[1])
row("type(EState.a) / Holder().handler / instance.a", lambda: (type(EState.a).__name__, type(Holder().handler).__name__, type(Holder().cb).__name__, type(new(EState).a).__name__))
row("Holder().handler is EState.a", lambda: Holder().handler is EState.a)
row("rx.button(on_click=Holder().handler)", lambda: len(rx.button(on_click=Holder().handler).event_triggers["on_click"].events))
row("rx.button(on_click=Holder().cb)", lambda: len(rx.button(on_click=Holder().cb).event_triggers["on_click"].events))
