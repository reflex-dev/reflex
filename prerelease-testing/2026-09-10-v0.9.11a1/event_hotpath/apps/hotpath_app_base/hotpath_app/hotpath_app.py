"""Event hot-path exercise app for reflex 0.9.11a1 (PR #7025).

Env toggles (read at import time):
  HP_TASK_FACTORY=1  install a custom asyncio task factory via a lifespan task (3.12+ eager start must be skipped)
  HP_GWT=1           add a backend var literally named `_get_was_touched` (the PR's own unit-test case) to BackendState
"""

from __future__ import annotations

import asyncio
import datetime
import itertools
import json
import os
import sys
import time

import reflex as rx

assert "/envs/" in rx.__file__, rx.__file__  # never the checkout

SEQ = itertools.count(1)
RECOMPUTE: dict[str, int] = {"ticks": 0, "ticks_td": 0, "cached_plain": 0, "mixin_ticks": 0, "clock_a": 0, "clock_b": 0}
FACTORY = {"installed": False, "n": 0}


def tag(s: str) -> str:
    return f"{next(SEQ)}:{s}"


class CounterState(rx.State):
    count: int = 0

    @rx.event
    def increment(self):
        self.count += 1

    @rx.event
    async def increment_async(self):
        # async handler with no await: with eager_start the task completes inside Task()
        self.count += 1

    @rx.event
    def reset_count(self):
        self.count = 0

    @rx.var(cache=False)
    def factory_info(self) -> str:
        return json.dumps({"py": sys.version.split()[0], **FACTORY, "loop_factory": bool(asyncio.get_event_loop().get_task_factory())})


class OtherState(rx.State):
    other_val: int = 0
    other_log: list[str] = []

    @rx.event
    def bump(self, who: str = ""):
        self.other_val += 1
        self.other_log.append(tag(f"bump:{who}"))

    @rx.event
    def clear_other(self):
        self.other_val = 0
        self.other_log = []


class OrderingState(rx.State):
    log: list[str] = []

    @rx.event
    def clear(self):
        self.log = []

    @rx.event
    async def multi_yield(self):
        for i in range(3):
            self.log.append(tag(f"my{i}"))
            yield
            await asyncio.sleep(0.15)

    @rx.event
    def chain(self):
        self.log.append(tag("chain-start"))
        return [OtherState.bump("from-chain"), OrderingState.after_chain()]

    @rx.event
    def after_chain(self):
        self.log.append(tag("after-chain"))

    @rx.event
    async def yield_other(self):
        self.log.append(tag("yo-start"))
        yield OtherState.bump("yield-other")
        self.log.append(tag("yo-end"))

    @rx.event
    async def yield_sleep_yield(self):
        self.log.append(tag("ysy-a"))
        yield
        await asyncio.sleep(0.4)
        self.log.append(tag("ysy-b"))
        yield
        await asyncio.sleep(0.3)
        self.log.append(tag("ysy-c"))

    @rx.event
    def click_a(self):
        self.log.append(tag("A"))

    @rx.event
    def click_b(self):
        self.log.append(tag("B"))

    @rx.event
    def fg_append(self, who: str):
        self.log.append(tag(f"fg:{who}"))

    @rx.event(background=True)
    async def bg_task(self):
        async with self:
            self.log.append(tag("bg-start"))
        await asyncio.sleep(0.6)
        async with self:
            other = await self.get_state(OtherState)
            gvv = await self.get_var_value(OtherState.other_val)
            other.other_val += 100
            self.log.append(tag(f"bg-mid other_val={other.other_val} gvv={gvv} parent={type(self.parent_state).__name__}"))
        await asyncio.sleep(0.3)
        async with self:
            self.log.append(tag("bg-end"))


class Root3(rx.State):
    root_val: int = 1


class Mid3(Root3):
    mid_val: int = 10


class Leaf3(Mid3):
    leaf_val: int = 100
    report: str = ""

    @rx.event
    def read_parents(self):
        p = self.parent_state
        gp = p.parent_state
        self.report = (
            f"leaf={self.leaf_val} mid={p.mid_val} root={gp.root_val} "
            f"inh_mid={self.mid_val} inh_root={self.root_val} "
            f"pname={p.get_name()} gpname={gp.get_name()} full={self.get_full_name()}"
        )

    @rx.event
    def write_via_parent(self):
        self.parent_state.mid_val += 1
        self.parent_state.parent_state.root_val += 1

    @rx.event
    def write_inherited(self):
        self.mid_val += 1
        self.root_val += 1

    @rx.event(background=True)
    async def bg_read_parents(self):
        async with self:
            p = self.parent_state
            self.report = f"bg leaf={self.leaf_val} mid={p.mid_val} root={p.parent_state.root_val} dirty={sorted(self.dirty_vars)}"
            self.leaf_val += 1


class TimeMixin(rx.State, mixin=True):
    @rx.var(interval=1)
    def mixin_ticks(self) -> str:
        RECOMPUTE["mixin_ticks"] += 1
        return f"{time.time():.3f}"


class IntervalState(TimeMixin, rx.State):
    base: int = 0
    bg_log: list[str] = []

    @rx.event
    def poke(self):
        pass

    @rx.event
    def bump_base(self):
        self.base += 1

    @rx.event
    def clear_bg(self):
        self.bg_log = []

    @rx.var(interval=1)
    def ticks(self) -> str:
        RECOMPUTE["ticks"] += 1
        return f"{time.time():.3f}"

    @rx.var(cache=True, interval=datetime.timedelta(seconds=1))
    def ticks_td(self) -> str:
        RECOMPUTE["ticks_td"] += 1
        return f"{time.time():.3f}"

    @rx.var(cache=True)
    def cached_plain(self) -> int:
        RECOMPUTE["cached_plain"] += 1
        return self.base * 2

    @rx.var(cache=False)
    def counts(self) -> str:
        return json.dumps(RECOMPUTE, sort_keys=True)

    @rx.event(background=True)
    async def bg_read_interval(self):
        async with self:
            t0 = self.ticks
            self.bg_log.append(f"bg t0={t0} counts={json.dumps(RECOMPUTE, sort_keys=True)}")
        await asyncio.sleep(1.5)
        async with self:
            t1 = self.ticks
            self.bg_log.append(f"bg t1={t1} changed={t1 != t0} counts={json.dumps(RECOMPUTE, sort_keys=True)}")


class Clock(rx.ComponentState):
    """ComponentState with an interval var: every create() makes a new state class."""

    label: str = ""

    @rx.var(interval=1)
    def now(self) -> str:
        RECOMPUTE[f"clock_{self.label or 'x'}"] = RECOMPUTE.get(f"clock_{self.label or 'x'}", 0) + 1
        return f"{time.time():.3f}"

    @rx.event
    def set_label_(self, v: str):
        self.label = v

    @classmethod
    def get_component(cls, label: str, **props):
        return rx.hstack(
            rx.button(f"label {label}", on_click=cls.set_label_(label), id=f"clock_{label}_set"),
            rx.text(f"clock_{label}=", cls.now, id=f"clock_{label}"),
        )


class SlowState(rx.State):
    slow_done: int = 0
    fast_count: int = 0
    boom_count: int = 0

    @rx.event
    async def slow(self):
        await asyncio.sleep(5)
        self.slow_done += 1

    @rx.event
    def fast(self):
        self.fast_count += 1

    @rx.event
    def boom(self):
        self.boom_count += 1
        msg = "intentional boom from SlowState.boom"
        raise ValueError(msg)

    @rx.event
    async def boom_async(self):
        # raises before its first await: with eager_start this happens inside Task()
        self.boom_count += 1
        msg = "intentional async boom from SlowState.boom_async"
        raise ValueError(msg)

    @rx.event
    def reset_slow(self):
        self.slow_done = 0
        self.fast_count = 0
        self.boom_count = 0


_backend_body: dict = {"__annotations__": {"_hidden": int, "_items": list[int], "shown": str}, "_hidden": 0, "_items": [], "shown": ""}
if os.environ.get("HP_GWT"):
    _backend_body["__annotations__"]["_get_was_touched"] = int
    _backend_body["_get_was_touched"] = 7


def bump_hidden(self):
    self._hidden += 1
    self._items.append(self._hidden)
    gwt = getattr(self, "_get_was_touched", None)
    if isinstance(gwt, int):
        self._get_was_touched = gwt + 1
    keys = sorted(self._backend_vars)
    self.shown = f"hidden={self._hidden} items={list(self._items)} gwt={getattr(self, '_get_was_touched', None) if isinstance(gwt, int) else 'n/a'} keys={keys}"


def reset_backend(self):
    self._hidden = 0
    self._items = []
    self.shown = ""


_backend_body["bump_hidden"] = rx.event(bump_hidden)
_backend_body["reset_backend"] = rx.event(reset_backend)
_backend_body["__module__"] = __name__
_backend_body["__qualname__"] = "BackendState"
BackendState = type("BackendState", (rx.State,), _backend_body)


class ShadowState(rx.State):
    """A public var named like a fast-pathed framework method (`get_state`)."""

    get_state: str = "shadow-initial"  # pyright: ignore[reportIncompatibleMethodOverride]
    note: str = ""

    @rx.event
    def set_shadow(self):
        self.get_state = f"set-{time.time():.0f}"
        self.note = f"fast={sorted(getattr(type(self), '_fast_attr_names', frozenset()) & {'get_state', 'get_delta', 'dirty_vars'})}"


class ShadowDeltaState(rx.State):
    """A public var named `get_delta` (a framework method called on every event)."""

    get_delta: int = 0  # pyright: ignore[reportIncompatibleMethodOverride]

    @rx.event
    def bump_delta(self):
        self.get_delta += 1


def nav() -> rx.Component:
    return rx.hstack(
        rx.link("counter", href="/"),
        rx.link("ordering", href="/ordering"),
        rx.link("hier", href="/hier"),
        rx.link("interval", href="/interval"),
        rx.link("slow", href="/slow"),
        rx.link("backend", href="/backend"),
        rx.link("shadow", href="/shadow"),
        spacing="4",
    )


def index() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("counter"),
        rx.text("count=", CounterState.count, id="count"),
        rx.button("increment", on_click=CounterState.increment, id="inc"),
        rx.button("increment_async", on_click=CounterState.increment_async, id="inc_async"),
        rx.button("reset", on_click=CounterState.reset_count, id="reset"),
        rx.text("factory=", CounterState.factory_info, id="factory"),
    )


def ordering() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("ordering"),
        rx.hstack(
            rx.button("multi_yield", on_click=OrderingState.multi_yield, id="multi_yield"),
            rx.button("chain", on_click=OrderingState.chain, id="chain"),
            rx.button("yield_other", on_click=OrderingState.yield_other, id="yield_other"),
            rx.button("ysy", on_click=OrderingState.yield_sleep_yield, id="ysy"),
            rx.button("A", on_click=OrderingState.click_a, id="a"),
            rx.button("B", on_click=OrderingState.click_b, id="b"),
            rx.button("bg", on_click=OrderingState.bg_task, id="bg"),
            rx.button("fg1", on_click=OrderingState.fg_append("1"), id="fg1"),
            rx.button("fg2", on_click=OrderingState.fg_append("2"), id="fg2"),
            rx.button("fg3", on_click=OrderingState.fg_append("3"), id="fg3"),
            rx.button("clear", on_click=[OrderingState.clear, OtherState.clear_other], id="clear"),
            wrap="wrap",
        ),
        rx.text("log=", OrderingState.log.join(","), id="log"),
        rx.text("other_val=", OtherState.other_val, id="other_val"),
        rx.text("other_log=", OtherState.other_log.join(","), id="other_log"),
    )


def hier() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("hier"),
        rx.hstack(
            rx.button("read_parents", on_click=Leaf3.read_parents, id="read_parents"),
            rx.button("write_via_parent", on_click=Leaf3.write_via_parent, id="write_via_parent"),
            rx.button("write_inherited", on_click=Leaf3.write_inherited, id="write_inherited"),
            rx.button("bg_read_parents", on_click=Leaf3.bg_read_parents, id="bg_read_parents"),
        ),
        rx.text("root_val=", Root3.root_val, id="root_val"),
        rx.text("mid_val=", Mid3.mid_val, id="mid_val"),
        rx.text("leaf_val=", Leaf3.leaf_val, id="leaf_val"),
        rx.text("leaf_inh_root=", Leaf3.root_val, id="leaf_inh_root"),
        rx.text("report=", Leaf3.report, id="report"),
    )


def interval() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("interval"),
        rx.hstack(
            rx.button("poke", on_click=IntervalState.poke, id="poke"),
            rx.button("bump_base", on_click=IntervalState.bump_base, id="bump_base"),
            rx.button("bg_read_interval", on_click=IntervalState.bg_read_interval, id="bg_read_interval"),
            rx.button("clear_bg", on_click=IntervalState.clear_bg, id="clear_bg"),
        ),
        rx.text("base=", IntervalState.base, id="base"),
        rx.text("ticks=", IntervalState.ticks, id="ticks"),
        rx.text("ticks_td=", IntervalState.ticks_td, id="ticks_td"),
        rx.text("mixin_ticks=", IntervalState.mixin_ticks, id="mixin_ticks"),
        rx.text("cached_plain=", IntervalState.cached_plain, id="cached_plain"),
        rx.text("counts=", IntervalState.counts, id="counts"),
        rx.text("bg_log=", IntervalState.bg_log.join(" | "), id="bg_log"),
        Clock.create("a"),
        Clock.create("b"),
    )


def slow() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("slow"),
        rx.hstack(
            rx.button("slow", on_click=SlowState.slow, id="slow"),
            rx.button("fast", on_click=SlowState.fast, id="fast"),
            rx.button("boom", on_click=SlowState.boom, id="boom"),
            rx.button("boom_async", on_click=SlowState.boom_async, id="boom_async"),
            rx.button("reset", on_click=SlowState.reset_slow, id="reset_slow"),
        ),
        rx.text("slow_done=", SlowState.slow_done, id="slow_done"),
        rx.text("fast_count=", SlowState.fast_count, id="fast_count"),
        rx.text("boom_count=", SlowState.boom_count, id="boom_count"),
    )


def backend() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("backend"),
        rx.hstack(
            rx.button("bump_hidden", on_click=BackendState.bump_hidden, id="bump_hidden"),
            rx.button("reset_backend", on_click=BackendState.reset_backend, id="reset_backend"),
        ),
        rx.text("shown=", BackendState.shown, id="shown"),
    )


def shadow() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("shadow"),
        rx.hstack(
            rx.button("set_shadow", on_click=ShadowState.set_shadow, id="set_shadow"),
            rx.button("bump_delta", on_click=ShadowDeltaState.bump_delta, id="bump_delta"),
        ),
        rx.text("get_state=", ShadowState.get_state, id="shadow_get_state"),
        rx.text("note=", ShadowState.note, id="shadow_note"),
        rx.text("get_delta=", ShadowDeltaState.get_delta, id="shadow_get_delta"),
    )


app = rx.App()
app.add_page(index, route="/")
app.add_page(ordering, route="/ordering")
app.add_page(hier, route="/hier")
app.add_page(interval, route="/interval")
app.add_page(slow, route="/slow")
app.add_page(backend, route="/backend")
app.add_page(shadow, route="/shadow")

if os.environ.get("HP_TASK_FACTORY"):

    def _counting_factory(loop, coro, **kwargs):
        FACTORY["n"] += 1
        return asyncio.Task(coro, loop=loop, **kwargs)

    async def install_task_factory():
        asyncio.get_running_loop().set_task_factory(_counting_factory)
        FACTORY["installed"] = True

    app.register_lifespan_task(install_task_factory)
