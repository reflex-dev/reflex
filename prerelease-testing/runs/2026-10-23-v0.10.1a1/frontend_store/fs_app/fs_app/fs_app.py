"""frontend_store QA app: structural sharing (#7273), shared store (#7441),
hook order (#7586), compiled-JS fixes (#7565 #7518 #7544 #7587 #7405).

Every mutating handler bumps `step` and writes the backend truth
(`self.dict()`) to $FS_TRUTH so the driver can compare the DOM against the
real state after each step.
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime
import json
import os
from pathlib import Path
from typing import Any

import pydantic
import reflex as rx
from reflex_base.vars.base import VarData
from reflex_base.vars import get_unique_variable_name
from reflex.utils.format import json_dumps

assert f"/envs/{os.environ.get('EXPECT_VENV', 'new')}/" in rx.__file__, rx.__file__

TRUTH = os.environ.get("FS_TRUTH", "/tmp/fs_truth.json")


@dataclasses.dataclass
class Item:
    id: int
    name: str
    qty: int
    tags: list[str]
    meta: dict[str, int]


@dataclasses.dataclass
class Inner:
    v: int = 0


@dataclasses.dataclass
class BaseThing:
    v: int = 0
    label: str = "b"
    inner: Inner = dataclasses.field(default_factory=Inner)


class PydThing(pydantic.BaseModel):
    v: int = 0
    label: str = "p"


def _items() -> list[Item]:
    return [
        Item(1, "one", 1, ["a"], {"k": 1}),
        Item(2, "two", 2, ["b", "c"], {}),
        Item(3, "three", 3, [], {"z": 26}),
    ]


class ShareState(rx.State):
    step: int = 0
    items: rx.Field[list[Item]] = rx.field(default_factory=_items)
    nested: dict[str, dict[str, int]] = {"a": {"x": 1, "y": 2}}
    blob: dict[str, int] | None = {"z": 1}
    poly: list[int] | dict[str, int] = [1, 2]
    matrix: list[list[int]] = [[1, 2], [3, 4]]
    bases: list[BaseThing] = [BaseThing(v=1), BaseThing(v=2)]
    pyd: list[PydThing] = [PydThing(v=1), PydThing(v=2)]
    when: datetime.datetime = datetime.datetime(2026, 10, 23, 12, 0, 0)
    tags: set[str] = {"s1", "s2"}
    pair: tuple[int, str] = (1, "one")
    big: list[int] = []
    next_id: int = 4

    @rx.var
    def summary(self) -> dict[str, Any]:
        return {
            "count": len(self.items),
            "names": [i.name for i in self.items],
            "by_qty": {i.name: i.qty for i in self.items},
            "nested_keys": sorted(self.nested),
        }

    @rx.var
    def big_len(self) -> int:
        return len(self.big)

    @rx.var
    def big_sum(self) -> int:
        return sum(self.big)

    def _record(self):
        Path(TRUTH).write_text(json_dumps({"step": self.step, "state": self.dict()}))

    def _done(self):
        self.step += 1
        self._record()

    @rx.event
    def op(self, name: str):
        getattr(self, f"_op_{name}")()
        self._done()

    def _op_append(self):
        self.items.append(Item(self.next_id, f"item{self.next_id}", self.next_id, ["n"], {"n": self.next_id}))
        self.next_id += 1

    def _op_pop(self):
        self.items.pop()

    def _op_pop0(self):
        self.items.pop(0)

    def _op_insert1(self):
        self.items.insert(1, Item(self.next_id, f"ins{self.next_id}", 0, ["i"], {}))
        self.next_id += 1

    def _op_sort_qty(self):
        self.items.sort(key=lambda i: i.qty)

    def _op_sort_qty_desc(self):
        self.items.sort(key=lambda i: -i.qty)

    def _op_reverse(self):
        self.items.reverse()

    def _op_clear(self):
        self.items.clear()

    def _op_reset(self):
        self.items = _items()
        self.next_id = 4

    def _op_replace_equal(self):
        # Equal-but-new object: structural sharing should keep identity.
        self.items[0] = Item(**dataclasses.asdict(self.items[0]))

    def _op_bump0(self):
        self.items[0].qty += 1

    def _op_tag0(self):
        self.items[0].tags.append("t")

    def _op_meta0(self):
        self.items[0].meta["k"] = self.items[0].meta.get("k", 0) + 10

    def _op_meta0_del(self):
        self.items[0].meta.pop("k", None)

    def _op_rename_last(self):
        self.items[-1].name = self.items[-1].name + "!"

    def _op_nested_add(self):
        self.nested["b"] = {"x": 1}

    def _op_nested_upd(self):
        self.nested["a"]["x"] += 1

    def _op_nested_del(self):
        del self.nested["a"]

    def _op_nested_del_inner(self):
        if "b" in self.nested:
            self.nested["b"].pop("x", None)

    def _op_nested_reset(self):
        self.nested = {"a": {"x": 1, "y": 2}}

    def _op_nested_reorder(self):
        # Same keys and values, different key order.
        self.nested = {k: self.nested[k] for k in reversed(list(self.nested))}

    def _op_blob_none(self):
        self.blob = None

    def _op_blob_dict(self):
        self.blob = {"z": 2, "w": 3}

    def _op_poly_obj(self):
        self.poly = {"a": 1}

    def _op_poly_arr(self):
        self.poly = [1, 2, 3]

    def _op_matrix_mut(self):
        self.matrix[1][0] = 9

    def _op_matrix_row(self):
        self.matrix.append([7, 7])

    def _op_matrix_pop_inner(self):
        self.matrix[0].pop()

    def _op_bases_mut(self):
        self.bases[0].inner.v += 1

    def _op_bases_replace(self):
        b = self.bases[0]
        self.bases[0] = BaseThing(v=b.v, label=b.label, inner=Inner(v=b.inner.v))

    def _op_pyd_mut(self):
        self.pyd[0].v += 1

    def _op_when_tick(self):
        self.when = self.when + datetime.timedelta(minutes=1)

    def _op_tags_add(self):
        self.tags.add("s3")

    def _op_tags_rm(self):
        self.tags.discard("s1")

    def _op_pair_swap(self):
        self.pair = (self.pair[0] + 1, self.pair[1] + "+")

    def _op_big_fill(self):
        self.big = list(range(5000))

    def _op_big_mut_mid(self):
        self.big[2500] = -1

    def _op_big_append(self):
        self.big.append(5000)

    def _op_big_pop0(self):
        self.big.pop(0)

    def _op_same_twice(self):
        # Assign the same value twice; nothing changes.
        q = self.items[0].qty
        self.items[0].qty = q
        self.items[0].qty = q

    def _op_set_same_nested(self):
        self.nested = json.loads(json.dumps(self.nested))

    def _op_noop(self):
        pass

    def _op_many(self):
        self._op_append()
        self._op_bump0()
        self._op_nested_add()
        self._op_matrix_mut()
        self._op_tags_add()
        self._op_reverse()

    @rx.event(background=True)
    async def bg_run(self):
        for i in range(5):
            async with self:
                self.items.append(Item(self.next_id, f"bg{i}", 100 + i, ["bg"], {"i": i}))
                self.next_id += 1
                self.nested["a"] = {"x": i, "bg": 1}
                if i % 2 == 0:
                    self.items[0].qty += 1
                self.step += 1
                self._record()
            await asyncio.sleep(0.05)


class SubA(ShareState):
    a: int = 0

    @rx.event
    async def both(self):
        self.a += 1
        b = await self.get_state(SubB)
        b.b += 10
        root = await self.get_state(ShareState)
        root.step += 1
        root._record()


class SubB(ShareState):
    b: int = 0


class Deep1(SubB):
    d1: int = 1


class Deep2(Deep1):
    d2: int = 2


class Deep3(Deep2):
    d3: int = 3

    @rx.event
    async def deep_bump(self):
        self.d3 += 1
        self.d1 += 1
        p = await self.get_state(SubB)
        p.b += 1
        root = await self.get_state(ShareState)
        root.step += 1
        root._record()


class RenderCounter(rx.el.Span):
    """Hoists a render counter hook into the enclosing component function."""

    counter: rx.Var[str]

    def add_imports(self):
        return {"react": "useRef"}

    def add_hooks(self):
        ref = get_unique_variable_name()
        self._ref_name = ref
        return [
            f"const {ref} = useRef(0); {ref}.current += 1;",
        ]

    def _render(self, *args, **kwargs):
        tag = super()._render(*args, **kwargs)
        tag = tag.add_props(**{"data-renders": rx.Var(f"String({self._ref_name}.current)")})
        return tag


@rx.memo
def item_card(item: rx.vars.ObjectVar[Item]) -> rx.Component:
    return rx.el.div(
        RenderCounter.create(counter="card"),
        rx.el.span(item.id, class_name="card-id"),
        rx.el.span(item.name, class_name="card-name"),
        rx.el.span(item.qty, class_name="card-qty"),
        rx.el.span(item.tags.join(","), class_name="card-tags"),
        rx.el.span(item.meta.to_string(), class_name="card-meta"),
        class_name="card",
    )


def _ops_buttons():
    ops = [
        "append", "pop", "pop0", "insert1", "sort_qty", "sort_qty_desc", "reverse", "clear", "reset",
        "replace_equal", "bump0", "tag0", "meta0", "meta0_del", "rename_last",
        "nested_add", "nested_upd", "nested_del", "nested_del_inner", "nested_reset", "nested_reorder",
        "blob_none", "blob_dict", "poly_obj", "poly_arr",
        "matrix_mut", "matrix_row", "matrix_pop_inner", "bases_mut", "bases_replace", "pyd_mut",
        "when_tick", "tags_add", "tags_rm", "pair_swap",
        "big_fill", "big_mut_mid", "big_append", "big_pop0",
        "same_twice", "set_same_nested", "noop", "many",
    ]
    return rx.el.div(
        *[rx.el.button(op, id=f"op-{op}", on_click=ShareState.op(op)) for op in ops],
        rx.el.button("bg_run", id="op-bg_run", on_click=ShareState.bg_run),
        rx.el.button("both", id="op-both", on_click=SubA.both),
        rx.el.button("deep_bump", id="op-deep_bump", on_click=Deep3.deep_bump),
    )


def _dump(name: str, var) -> rx.Component:
    return rx.el.pre(var.to_string(), id=f"v-{name}")


def index() -> rx.Component:
    return rx.el.div(
        rx.el.div(rx.State.is_hydrated.to_string(), id="hydrated"),
        rx.el.div(ShareState.step, id="step"),
        _ops_buttons(),
        _dump("items", ShareState.items),
        _dump("nested", ShareState.nested),
        _dump("blob", ShareState.blob),
        _dump("poly", ShareState.poly),
        _dump("matrix", ShareState.matrix),
        _dump("bases", ShareState.bases),
        _dump("pyd", ShareState.pyd),
        _dump("when", ShareState.when),
        _dump("tags", ShareState.tags),
        _dump("pair", ShareState.pair),
        _dump("summary", ShareState.summary),
        _dump("big_len", ShareState.big_len),
        _dump("big_sum", ShareState.big_sum),
        rx.el.pre(ShareState.big.length(), id="v-big_js_len"),
        rx.el.pre(ShareState.big[2500], id="v-big_2500"),
        _dump("a", SubA.a),
        _dump("b", SubB.b),
        _dump("d1", Deep3.d1),
        _dump("d3", Deep3.d3),
        rx.el.div(
            rx.cond(
                ShareState.nested.contains("a") & (ShareState.nested["a"]["x"] > 1),
                "big",
                "small",
            ),
            id="cond-nested",
        ),
        rx.el.div(rx.cond(ShareState.blob, "has-blob", "no-blob"), id="cond-blob"),
        rx.el.ul(
            rx.foreach(
                ShareState.items,
                lambda item, i: rx.el.li(
                    i, "|", item.id, "|", item.name, "|", item.qty, "|",
                    item.tags.join(","), "|", item.meta.to_string(),
                ),
            ),
            id="idx",
        ),
        rx.el.ul(
            rx.foreach(
                ShareState.items,
                lambda item: rx.el.li(
                    item.id, "|", item.name, "|", item.qty, "|",
                    item.tags.join(","), "|", item.meta.to_string(),
                    key=item.id.to_string(),
                ),
            ),
            id="keyed",
        ),
        rx.el.ul(
            rx.foreach(
                ShareState.nested,
                lambda kv: rx.el.li(kv[0], "=", kv[1].to_string()),
            ),
            id="nested-entries",
        ),
        rx.el.div(rx.foreach(ShareState.items, lambda item: item_card(item=item)), id="cards"),
        rx.el.ul(rx.foreach(ShareState.matrix, lambda row: rx.el.li(row.join(","))), id="matrix-rows"),
        rx.el.ul(rx.foreach(ShareState.big, lambda n: rx.el.li(n)), id="big-list"),
        rx.el.a("hooks", href="/hooks", id="to-hooks"),
        rx.el.a("js", href="/js", id="to-js"),
        rx.el.a("dyn", href="/dyn/42", id="to-dyn"),
    )


# ---- /hooks -----------------------------------------------------------------


class HookState(rx.State):
    count: int = 1
    pasted: str = ""
    size: str = ""
    key: str = ""
    cs_val: str = ""
    show_reader: bool = False

    @rx.event
    def inc(self):
        self.count += 1

    @rx.event
    def on_paste(self, data: list[tuple[str, str]]):
        self.pasted = json.dumps(data)

    @rx.event
    def on_resize(self, w: int, h: int):
        self.size = f"{w}x{h}"

    @rx.event
    def on_key(self, key: str):
        self.key = key

    @rx.event
    def got_cs(self, v):
        self.cs_val = str(v)

    @rx.event
    def toggle_reader(self):
        self.show_reader = not self.show_reader

    @rx.event
    def push_cs(self, value: int):
        return cs_count.push(value)


class HookReader(rx.el.Span):
    """add_hooks reading state through a Var (dependency hook) and a plain string."""

    def add_imports(self):
        return {"react": "useRef"}

    def add_hooks(self):
        return [
            rx.Var(f"const hr_doubled = {HookState.count} * 2;"),
            "const hr_plain = hr_doubled + 1; if (typeof window !== 'undefined') window.__hr_plain = hr_plain;",
        ]

    def _render(self, *args, **kwargs):
        tag = super()._render(*args, **kwargs)
        tag = tag.add_props(**{
            "data-doubled": rx.Var("String(hr_doubled)"),
            "data-plain": rx.Var("String(hr_plain)"),
        })
        return tag


class HookReaderPositioned(rx.el.Span):
    """Same, but the hook carries the deprecated VarData(position=...)."""

    def add_hooks(self):
        return [
            rx.Var(
                f"const hr_pos = {HookState.count} + 100;",
                _var_data=VarData(position=rx.constants.Hooks.HookPosition.POST_TRIGGER),
            ),
            rx.Var(
                "const hr_pos_pre = hr_pos - 1;",
                _var_data=VarData(position=rx.constants.Hooks.HookPosition.PRE_TRIGGER),
            ),
        ]

    def _render(self, *args, **kwargs):
        tag = super()._render(*args, **kwargs)
        tag = tag.add_props(**{
            "data-pos": rx.Var("String(hr_pos)"),
            "data-pos-pre": rx.Var("String(hr_pos_pre)"),
        })
        return tag


class CustomCoder(rx.el.Span):
    def add_custom_code(self):
        return ["if (typeof window !== 'undefined') window.__custom_code_ran = (window.__custom_code_ran || 0) + 1;"]


class Counter(rx.ComponentState):
    count: int = 0

    @rx.event
    def inc(self):
        self.count += 1

    @classmethod
    def get_component(cls, **props):
        return rx.el.div(
            rx.el.span(cls.count, class_name="cs-count"),
            rx.el.button("inc", on_click=cls.inc, class_name="cs-inc"),
            **props,
        )


cs_count = rx._x.client_state(default=0, var_name="cs_count", global_ref=True)
cs_local = rx._x.client_state(default="loc", var_name="cs_local", global_ref=False)


@rx.memo
def memo_reader(item: rx.vars.ObjectVar[Item], suffix: rx.Var[str]) -> rx.Component:
    # Reads a prop (object) and a state var directly inside the memo.
    return rx.el.div(
        RenderCounter.create(counter="memo"),
        rx.el.span(item.name, class_name="mr-name"),
        rx.el.span(HookState.count, class_name="mr-count"),
        rx.el.span(suffix, class_name="mr-suffix"),
        class_name="memo-reader",
    )


class MemoHost(rx.State):
    thing: Item = Item(9, "memo-item", 9, ["m"], {"m": 9})
    unrelated: int = 0

    @rx.event
    def bump_unrelated(self):
        self.unrelated += 1

    @rx.event
    def rename_thing(self):
        self.thing.name = self.thing.name + "."


def hooks_page() -> rx.Component:
    return rx.el.div(
        rx.el.div(rx.State.is_hydrated.to_string(), id="hydrated"),
        rx.el.button("inc", id="inc", on_click=HookState.inc),
        rx.el.span(HookState.count, id="count"),
        HookReader.create(id="reader"),
        # On 0.10.0 the PRE/POST buckets emit hr_pos_pre before hr_pos -> ReferenceError (#7586)
        HookReaderPositioned.create(id="reader-pos") if os.environ.get("FS_POSITIONED", "1") == "1" else rx.fragment(),
        CustomCoder.create(id="coder"),
        rx.window_event_listener(on_resize=HookState.on_resize, on_key_down=HookState.on_key),
        rx.el.span(HookState.size, id="size"),
        rx.el.span(HookState.key, id="key"),
        rx.clipboard(on_paste=HookState.on_paste),
        rx.el.span(HookState.pasted, id="pasted"),
        rx.el.button(
            "call script",
            id="call-script",
            on_click=rx.call_script("window.__cs = 41 + 1; window.__cs", callback=HookState.got_cs),
        ),
        rx.el.span(HookState.cs_val, id="cs-val"),
        Counter.create(id="c1"),
        Counter.create(id="c2"),
        rx.el.button("cs+", id="cs-inc", on_click=cs_count.set_value(cs_count.value + 1)),
        rx.el.button("cs0", id="cs-zero", on_click=cs_count.set_value(0)),
        rx.el.button("push7", id="cs-push", on_click=HookState.push_cs(7)),
        rx.el.span(cs_count.value, id="cs-main"),
        rx.el.button("toggle reader", id="toggle-reader", on_click=HookState.toggle_reader),
        rx.cond(HookState.show_reader, rx.el.span(cs_count.value, id="cs-late")),
        rx.el.input(id="cs-local-in", default_value=cs_local.value, on_change=cs_local.set_value),
        rx.el.span(cs_local.value, id="cs-local"),
        memo_reader(item=MemoHost.thing, suffix="s"),
        rx.el.button("unrelated", id="unrelated", on_click=MemoHost.bump_unrelated),
        rx.el.button("rename thing", id="rename-thing", on_click=MemoHost.rename_thing),
        rx.el.span(MemoHost.unrelated, id="unrelated-val"),
        rx.el.a("index", href="/", id="to-index"),
    )


# ---- /js ----------------------------------------------------------------------

UNI = "héllo 👋🏽 wörld é 𝔘𝔫𝔦"


class JsState(rx.State):
    x: int = 3
    s: str = UNI
    n: str | None = None
    d: dict[str, Any] = {"a": [1, 2], "b": {"c": "d"}}

    @rx.event
    def set_x(self, v: int):
        self.x = v

    @rx.event
    def set_s(self, v: str):
        self.s = v

    @rx.event
    def set_n(self, v: str | None):
        self.n = v


def _at(s: str, i: int) -> str:
    # JS pyStrAt returns undefined (rendered as "") where Python raises IndexError.
    try:
        return s[i]
    except IndexError:
        return ""


def _py_expected(s: str, x: int) -> dict[str, Any]:
    return {
        "len": len(s),
        "at0": _at(s, 0),
        "at6": _at(s, 6),
        "at7": _at(s, 7),
        "atm1": _at(s, -1),
        "sl_1_4": s[1:4],
        "sl_6_8": s[6:8],
        "sl_m3": s[-3:],
        "sl_step2": s[::2],
        "neg_sq": (-x) ** 2,
        "neg_of_sq": -(x**2),
        "m5_sq": (x - 5) ** 2,
        "neg_cube": (-x) ** 3,
        "lit_neg_base": (-2) ** x,
        "none_len": 0,
    }


def js_page() -> rx.Component:
    s = JsState.s
    x = JsState.x
    exprs: dict[str, Any] = {
        "len": s.length(),
        "at0": s[0],
        "at6": s[6],
        "at7": s[7],
        "atm1": s[-1],
        "sl_1_4": s[1:4],
        "sl_6_8": s[6:8],
        "sl_m3": s[-3:],
        "sl_step2": s[::2],
        "neg_of_sq": -(x**2),
        "m5_sq": (x - 5) ** 2,
    }
    if os.environ.get("FS_NONELEN", "1") == "1":
        # .length() on a None str crashes the page on 0.10.0 (null.split); #7518
        exprs["none_len"] = JsState.n.length()
    if os.environ.get("FS_NEGSQ", "1") == "1":
        # (-x) ** 2 is a JS SyntaxError on 0.10.0 (#7565); gate so the prod
        # baseline build can still succeed.
        exprs["neg_sq"] = (-x) ** 2
        exprs["neg_cube"] = (-x) ** 3
        exprs["lit_neg_base"] = rx.Var.create(-2) ** x
    return rx.el.div(
        rx.el.div(rx.State.is_hydrated.to_string(), id="hydrated"),
        rx.el.pre(json.dumps(_py_expected(UNI, 3)), id="js-expected"),
        rx.el.pre(json.dumps(_py_expected("ab", 4)), id="js-expected-2"),
        *[rx.el.span(v, id=f"js-{k}") for k, v in exprs.items()],
        rx.el.button("set2", id="set2", on_click=[JsState.set_s("ab"), JsState.set_x(4)]),
        rx.el.button("set-n", id="set-n", on_click=JsState.set_n("xy")),
        rx.el.div(
            "styled",
            id="styled",
            class_name="text-red-500",
            style={"color": "blue", "padding": JsState.x.to_string() + "px"},
            custom_attrs={"data-dict": JsState.d.to_string()},
        ),
        rx.el.button(
            "err-noobj",
            id="err-noobj",
            on_click=rx.call_script(
                "window.dispatchEvent(new ErrorEvent('error', {message: 'ResizeObserver loop completed with undelivered notifications.', filename: 'http://localhost/x.js', lineno: 7, colno: 3}))"
            ),
        ),
        rx.el.button(
            "err-obj",
            id="err-obj",
            on_click=rx.call_script("setTimeout(() => { throw new Error('boom-with-object'); }, 0)"),
        ),
        rx.el.button(
            "err-onerror-direct",
            id="err-onerror-direct",
            on_click=rx.call_script("window.onerror('direct message only', 'http://localhost/y.js', 1, 2)"),
        ),
    )


class DynState(rx.State):
    @rx.var
    def where(self) -> str:
        return f"path={self.router.url.path}"


def dyn_page() -> rx.Component:
    return rx.el.div(
        rx.el.div(rx.State.is_hydrated.to_string(), id="hydrated"),
        rx.el.span(rx.State.router.page.params["pid"], id="pid"),
        rx.el.span(DynState.where, id="where"),
        rx.el.span(ShareState.step, id="step"),
        rx.el.span(HookState.count, id="count"),
        rx.el.a("index", href="/", id="to-index"),
    )


app = rx.App()
app.add_page(index, route="/")
app.add_page(hooks_page, route="/hooks")
app.add_page(js_page, route="/js")
app.add_page(dyn_page, route="/dyn/[pid]")
