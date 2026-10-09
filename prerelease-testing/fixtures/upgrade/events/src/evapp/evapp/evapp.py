"""events_vars cluster app: event-loop semantics, Var operations, state API edge cases.

Runs on reflex 0.10.0a2 (alpha2, under test), 0.10.0a1 and, for baselines, 0.9.12 (stable).
0.10-only features are guarded by IS_ALPHA so the same module compiles on all of them.
(events2 copy: adds the /priv page for #7465.)
"""

import asyncio
import dataclasses
import functools
import importlib.metadata
import json
import os
import time
import traceback

import reflex as rx

# venv guard (a3_events_tp): bin/start.sh exports EV_EXPECT_VENV=<venv name>
_EXPECT_VENV = __import__("os").environ.get("EV_EXPECT_VENV", "")
assert _EXPECT_VENV and f"/envs/{_EXPECT_VENV}/" in rx.__file__, (rx.__file__, _EXPECT_VENV)
print(f"VENV_GUARD ok venv={_EXPECT_VENV} reflex={rx.__file__}", flush=True)
from reflex.event import EventSpec
from reflex.utils.imports import ImportVar
from reflex.vars import VarData

REFLEX_VERSION = importlib.metadata.version("reflex")
IS_ALPHA = REFLEX_VERSION.startswith("0.10")
EXC = {"backend": 0, "frontend": 0}


def evlog(msg: str) -> None:
    """Print a greppable marker line to the server log."""
    print(f"EVLOG {time.time():.3f} {msg}", flush=True)


# exception handlers
def ev_backend_exc(exception: Exception) -> EventSpec | None:
    """Count backend exceptions and record them in state."""
    EXC["backend"] += 1
    evlog(f"BACKEND_EXC #{EXC['backend']} {type(exception).__name__}: {exception}")
    tb = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__)[-4:])
    evlog("BACKEND_EXC_TB " + tb.replace("\n", " \\n "))
    return ExcState.record_backend(f"{type(exception).__name__}: {str(exception)[:80]}")


def ev_frontend_exc(exception: Exception) -> None:
    """Count frontend exceptions reported by the browser."""
    EXC["frontend"] += 1
    evlog(f"FRONTEND_EXC #{EXC['frontend']} {type(exception).__name__}: {str(exception)[:200]}")


class ExcState(rx.State):
    """Holds exception-handler observations."""

    backend_errors: list[str] = []
    counts: str = ""

    @rx.event
    def record_backend(self, msg: str):
        self.backend_errors.append(msg)

    @rx.event
    def refresh_counts(self):
        self.counts = f"backend={EXC['backend']} frontend={EXC['frontend']}"

    @rx.event
    def clear(self):
        self.backend_errors = []


def exc_panel() -> rx.Component:
    return rx.vstack(
        rx.text(ExcState.backend_errors.length(), id="exc-count"),
        rx.text(ExcState.backend_errors.join(" | "), id="exc-list"),
        rx.button("refresh counts", on_click=ExcState.refresh_counts, id="exc-refresh"),
        rx.text(ExcState.counts, id="exc-counts"),
        rx.button("clear exc", on_click=ExcState.clear, id="exc-clear"),
    )


def nav() -> rx.Component:
    return rx.hstack(
        *[rx.link(p, href=f"/{p}", id=f"nav-{p}") for p in
          ["sup", "deco", "nested", "throttle", "vars", "typelog", "api", "bind", "priv"]],
        rx.text(REFLEX_VERSION, id="reflex-version"),
    )


# 1. supersedes
class SupState(rx.State):
    log: list[str] = []
    partial: list[str] = []
    bg_log: list[str] = []
    lock_log: list[str] = []
    cpu_log: list[str] = []
    gen_log: list[str] = []
    marks: list[str] = []

    @rx.event
    def clear(self):
        self.log = []
        self.partial = []
        self.bg_log = []
        self.lock_log = []
        self.cpu_log = []
        self.gen_log = []
        self.marks = []

    @rx.event(supersedes=True)
    async def slow(self, label: str):
        for i in range(5):
            self.log.append(f"{label}{i}")
            yield
            await asyncio.sleep(1)
        self.log.append(f"{label}done")

    @rx.event(supersedes=True)
    async def slow_partial(self, label: str):
        self.partial.append(f"{label}start")
        yield
        self.partial.append(f"{label}unflushed")
        await asyncio.sleep(3)
        self.partial.append(f"{label}end")

    @rx.event(background=True, supersedes=True)
    async def bg_sup(self, label: str):
        for i in range(5):
            async with self:
                self.bg_log.append(f"{label}{i}")
            await asyncio.sleep(1)
        async with self:
            self.bg_log.append(f"{label}done")

    @rx.event(background=True, supersedes=True)
    async def bg_sup_lock(self, label: str):
        async with self:
            self.lock_log.append(f"{label}in")
            await asyncio.sleep(2)
            self.lock_log.append(f"{label}in2")
        async with self:
            self.lock_log.append(f"{label}done")

    @rx.event
    def ping(self, label: str):
        self.marks.append(label)
        self.lock_log.append(f"ping-{label}")

    @rx.event(supersedes=True)
    def cpu_sup(self, label: str):
        self.cpu_log.append(f"{label}start")
        t0 = time.monotonic()
        while time.monotonic() - t0 < 1.5:
            pass
        self.cpu_log.append(f"{label}end")

    @rx.event(supersedes=True)
    def gen_sup(self, label: str):
        for i in range(4):
            self.gen_log.append(f"{label}{i}")
            yield
            time.sleep(0.6)
        self.gen_log.append(f"{label}done")

    @rx.event(supersedes=True)
    def chain_parent(self, label: str):
        self.log.append(f"{label}P")
        return ChainChild.slow_child(label)


class ChainChild(rx.State):
    child_log: list[str] = []

    @rx.event
    async def slow_child(self, label: str):
        for i in range(4):
            self.child_log.append(f"{label}{i}")
            yield
            await asyncio.sleep(1)
        self.child_log.append(f"{label}done")

    @rx.event
    def clear(self):
        self.child_log = []


class SupCounter(rx.ComponentState):
    log: list[str] = []

    @rx.event(supersedes=True)
    async def run(self, label: str):
        for i in range(3):
            self.log.append(f"{label}{i}")
            yield
            await asyncio.sleep(1)
        self.log.append(f"{label}done")

    @rx.event
    def clear(self):
        self.log = []

    @classmethod
    def get_component(cls, *children, name: str = "x", **props) -> rx.Component:
        return rx.hstack(
            rx.button(f"cs-{name}", on_click=cls.run(name), id=f"cs-run-{name}"),
            rx.button(f"cs-clear-{name}", on_click=cls.clear, id=f"cs-clear-{name}"),
            rx.text(cls.log.join(","), id=f"cs-log-{name}"),
        )


def sup_page() -> rx.Component:
    def row(label, handler, logvar, ids):
        return rx.hstack(
            *[rx.button(f"{label}-{x}", on_click=handler(x), id=f"{label}-{x}") for x in ids],
            rx.text(logvar.join(","), id=f"{label}-log"),
        )

    return rx.vstack(
        nav(),
        rx.heading("supersedes"),
        rx.button("clear", on_click=[SupState.clear, ChainChild.clear], id="sup-clear"),
        row("slow", SupState.slow, SupState.log, "abcd"),
        row("partial", SupState.slow_partial, SupState.partial, "abc"),
        row("bg", SupState.bg_sup, SupState.bg_log, "abcd"),
        row("lock", SupState.bg_sup_lock, SupState.lock_log, "abc"),
        row("ping", SupState.ping, SupState.marks, "123456"),
        row("cpu", SupState.cpu_sup, SupState.cpu_log, "abc"),
        row("gen", SupState.gen_sup, SupState.gen_log, "abc"),
        row("chain", SupState.chain_parent, ChainChild.child_log, "abc"),
        SupCounter.create(name="A"),
        SupCounter.create(name="B"),
        exc_panel(),
    )


# 2. decorator order (#7370)
TRACE: list[str] = []


def traced(fn):
    """A plain functools.wraps decorator, as a user or library would write."""

    @functools.wraps(fn)
    async def wrapper(self, *args, **kwargs):
        TRACE.append(fn.__name__)
        return await fn(self, *args, **kwargs)

    return wrapper


class DecoState(rx.State):
    log: list[str] = []

    @rx.event
    def clear(self):
        self.log = []

    @rx.event
    def fg_ping(self, label: str):
        self.log.append(f"ping{label}")

    async def late_bg(self):
        async with self:
            self.log.append("late:start")
        await asyncio.sleep(1.5)
        async with self:
            self.log.append("late:end")

    async def late_bg_after_read(self):
        async with self:
            self.log.append("lateread:start")
        await asyncio.sleep(1.5)
        async with self:
            self.log.append("lateread:end")

    @rx.event(background=True)
    @traced
    async def wrapped_inner(self):
        async with self:
            self.log.append("wrapinner:start")
        await asyncio.sleep(1.5)
        async with self:
            self.log.append("wrapinner:end")

    @traced
    @rx.event(background=True)
    async def wrapped_outer(self):
        async with self:
            self.log.append("wrapouter:start")
        await asyncio.sleep(1.5)
        async with self:
            self.log.append("wrapouter:end")

    @rx.event
    def trace_report(self):
        self.log.append("trace=" + "/".join(TRACE))


# Mark background after the class exists (class-level access first, nothing read is_background).
_ = DecoState.late_bg
setattr(DecoState.late_bg.fn, "_reflex_background_task", True)
# Mark background after is_background was already read (documented: cached on alpha).
_ = DecoState.late_bg_after_read.is_background
setattr(DecoState.late_bg_after_read.fn, "_reflex_background_task", True)


class BgMixin(rx.State, mixin=True):
    mix_log: list[str] = []

    @rx.event(background=True)
    async def mix_bg(self, label: str):
        async with self:
            self.mix_log.append(f"{label}:start")
        await asyncio.sleep(1.5)
        async with self:
            self.mix_log.append(f"{label}:end")

    @rx.event
    def mix_ping(self, label: str):
        self.mix_log.append(f"ping{label}")


class MixA(BgMixin, rx.State):
    pass


class MixB(BgMixin, rx.State):
    pass


class PkgState(rx.State):
    """Simulates a library state whose handler a user re-decorates as background."""

    pkg_log: list[str] = []

    async def pkg_work(self):
        async with self:
            self.pkg_log.append("pkg:start")
        await asyncio.sleep(1.5)
        async with self:
            self.pkg_log.append("pkg:end")

    @rx.event
    def pkg_ping(self):
        self.pkg_log.append("ping")


# A component referencing the handler is built BEFORE the re-decoration.
_pkg_early_button = rx.button("pkg-early", on_click=PkgState.pkg_work, id="pkg-early")
rx.event(PkgState.pkg_work.fn, background=True)


def deco_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("decorator order"),
        rx.button("clear", on_click=[DecoState.clear], id="deco-clear"),
        rx.button("late_bg", on_click=DecoState.late_bg, id="deco-late"),
        rx.button("late_bg_after_read", on_click=DecoState.late_bg_after_read, id="deco-lateread"),
        rx.button("wrapped_inner", on_click=DecoState.wrapped_inner, id="deco-wrapinner"),
        rx.button("wrapped_outer", on_click=DecoState.wrapped_outer, id="deco-wrapouter"),
        rx.button("ping", on_click=DecoState.fg_ping("1"), id="deco-ping1"),
        rx.button("ping2", on_click=DecoState.fg_ping("2"), id="deco-ping2"),
        rx.button("trace", on_click=DecoState.trace_report, id="deco-trace"),
        rx.text(DecoState.log.join(","), id="deco-log"),
        rx.button("mixA", on_click=MixA.mix_bg("A"), id="mix-a"),
        rx.button("mixB", on_click=MixB.mix_bg("B"), id="mix-b"),
        rx.button("mixA-ping", on_click=MixA.mix_ping("A"), id="mix-a-ping"),
        rx.text(MixA.mix_log.join(","), id="mix-a-log"),
        rx.text(MixB.mix_log.join(","), id="mix-b-log"),
        _pkg_early_button,
        rx.button("pkg-late", on_click=PkgState.pkg_work, id="pkg-late"),
        rx.button("pkg-ping", on_click=PkgState.pkg_ping, id="pkg-ping"),
        rx.text(PkgState.pkg_log.join(","), id="pkg-log"),
        exc_panel(),
    )


# 3. nested event lists (#7319)
class NestState(rx.State):
    order: list[str] = []
    key: str = "b"

    @rx.event
    def ev(self, name: str):
        self.order.append(name)

    @rx.event
    def boom(self):
        raise RuntimeError("boom-intentional")

    @rx.event
    def ret_nested(self):
        return [NestState.ev("A"), [NestState.ev("B"), [NestState.ev("C")]], NestState.ev("D")]

    @rx.event
    def yield_nested(self):
        yield [NestState.ev("Y1"), [NestState.ev("Y2")]]

    @rx.event
    def ret_flat_boom(self):
        return [NestState.ev("R1"), NestState.boom, NestState.ev("R2")]

    @rx.event
    def clear(self):
        self.order = []


def deep_match(n: int):
    inner = rx.match(NestState.key, ("b", [NestState.ev("Z0")]), rx.noop())
    for i in range(1, n):
        inner = rx.match(NestState.key, ("b", [NestState.ev(f"Z{i}"), inner]), rx.noop())
    return inner


def nested_page() -> rx.Component:
    m = NestState.key
    return rx.vstack(
        nav(),
        rx.heading("nested event lists"),
        rx.button("clear", on_click=[NestState.clear, ExcState.clear], id="nest-clear"),
        rx.text(NestState.order.join(","), id="nest-order"),
        rx.button("ordinary", on_click=NestState.ev("O"), id="nest-ordinary"),
        rx.button("match-nested", on_click=rx.match(m, ("b", [NestState.ev("M1"), NestState.ev("M2")]), rx.noop()), id="nest-match"),
        rx.button("deep50", on_click=deep_match(50), id="nest-deep50"),
        rx.button("boom-middle", on_click=[NestState.ev("P1"), NestState.boom, NestState.ev("P2"), NestState.ev("P3")], id="nest-boom-flat"),
        rx.button("boom-in-match", on_click=rx.match(m, ("b", [NestState.ev("Q1"), NestState.boom, NestState.ev("Q2")]), rx.noop()), id="nest-boom-match"),
        rx.button("malformed-5", on_click=rx.match(m, ("b", [NestState.ev("W1"), rx.Var.create(5), NestState.ev("W2")]), rx.noop()), id="nest-malformed"),
        rx.button("ret-nested", on_click=NestState.ret_nested, id="nest-ret"),
        rx.button("yield-nested", on_click=NestState.yield_nested, id="nest-yield"),
        rx.button("ret-flat-boom", on_click=NestState.ret_flat_boom, id="nest-ret-boom"),
        rx.button("cs-throw-middle", on_click=rx.match(m, ("b", [NestState.ev("C1"), rx.call_script("throw new Error('cs-boom')"), NestState.ev("C2")]), rx.noop()), id="nest-cs-throw"),
        rx.button("cs-callback-list", on_click=rx.call_script("'cbv'", callback=lambda r: [NestState.ev(r), NestState.ev("CB2")]), id="nest-cs-cb"),
        rx.button("run-script-middle", on_click=rx.match(m, ("b", [NestState.ev("RS1"), rx.run_script("window.__rs = (window.__rs || 0) + 1"), NestState.ev("RS2")]), rx.noop()), id="nest-rs"),
        rx.input(
            id="pd-input",
            placeholder="type x (prevented) / y",
            on_key_down=lambda key: rx.cond(
                key == "x",
                rx.match(
                    key,
                    ("x", [NestState.ev("PDX").prevent_default, NestState.ev("PDX2")]),
                    rx.noop(),
                ),
                rx.noop(),
            ),
        ),
        rx.window_event_listener(
            on_key_down=lambda key, modifiers: rx.cond(
                modifiers["ctrl_key"],
                rx.match(
                    key,
                    ("s", rx.noop()),
                    ("b", [NestState.ev("K1").stop_propagation.prevent_default, NestState.ev("K2")]),
                    rx.noop(),
                ),
                rx.noop(),
            ),
        ),
        exc_panel(),
    )


# 4. throttle / debounce / temporal
class TypeState(rx.State):
    received: list[str] = []
    applied: list[str] = []
    deb_received: list[str] = []

    @rx.event(throttle=200, supersedes=True)
    async def on_type(self, value: str):
        self.received.append(value)
        yield
        await asyncio.sleep(0.4)
        self.applied.append(value)

    @rx.event(debounce=300, supersedes=True)
    async def on_type_deb(self, value: str):
        self.deb_received.append(value)

    @rx.event
    def clear(self):
        self.received = []
        self.applied = []
        self.deb_received = []


class TempState(rx.State):
    hits: list[str] = []

    @rx.event(temporal=True)
    def temporal_hit(self, label: str):
        self.hits.append(f"T{label}")

    @rx.event
    def normal_hit(self, label: str):
        self.hits.append(f"N{label}")

    @rx.event
    def clear(self):
        self.hits = []


def throttle_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("throttle / debounce / temporal"),
        rx.button("clear", on_click=[TypeState.clear, TempState.clear], id="thr-clear"),
        rx.input(id="thr-input", on_change=TypeState.on_type),
        rx.text(TypeState.received.join("|"), id="thr-received"),
        rx.text(TypeState.applied.join("|"), id="thr-applied"),
        rx.input(id="deb-input", on_change=TypeState.on_type_deb),
        rx.text(TypeState.deb_received.join("|"), id="deb-received"),
        *[rx.button(f"t{i}", on_click=TempState.temporal_hit(str(i)), id=f"temp-t{i}") for i in range(1, 5)],
        *[rx.button(f"n{i}", on_click=TempState.normal_hit(str(i)), id=f"temp-n{i}") for i in range(1, 5)],
        rx.text(TempState.hits.join(","), id="temp-hits"),
        exc_panel(),
    )


# 5. Var operations
cs_dict = rx._x.client_state("cs_dict", default={"b": [3], "a": [1, 2]})


class VarState(rx.State):
    items: list[int] = list(range(10))
    step: int = 2
    a: int = 2
    b: int = 7
    s: str = "abcdefghij"
    emoji: str = "a\U0001f600b"
    d: dict[str, int] = {"x": 1, "y": 2, "z": 3}
    key: str = "y"
    rows: list[dict[str, str]] = [{"name": "b"}, {"name": "a"}, {"name": "c"}]
    left: dict[str, list[int]] = {"a": [1, 2], "b": [3]}

    @rx.var
    def comp1(self) -> dict[str, list[int]]:
        return {"a": [1, 2], "b": [3]}

    @rx.var
    def comp2(self) -> dict[str, list[int]]:
        return {"b": [3], "a": [1, 2]}

    @rx.event
    def set_step(self, v: int):
        self.step = v

    @rx.event
    def set_bounds(self, a: int, b: int):
        self.a = a
        self.b = b

    @rx.event
    def set_key(self, k: str):
        self.key = k

    @rx.event
    def mutate_left(self):
        self.left["a"].append(9)


class HookProbe(rx.Fragment):
    """Custom component whose hook Var goes through Var._replace(_var_data=...) (#7256)."""

    def add_hooks(self) -> list:
        hook = rx.Var('const [hookProbeValue] = useState("hook-ok");')._replace(
            _var_data=VarData(imports={"react": [ImportVar(tag="useState")]})
        )
        return [hook]


def _span(x):
    return rx.text(x, as_="span", margin_right="4px")


def vars_page() -> rx.Component:
    V = VarState
    alpha_only = []
    if IS_ALPHA:
        alpha_only = [
            rx.box(rx.foreach(V.items[:: V.step], _span), id="v-step-foreach"),
            rx.box(rx.foreach(V.items[V.b : V.a : -1], _span), id="v-ba-rev-foreach"),
            rx.text(V.s[:: V.step], id="v-s-step"),
            rx.text(V.items[:: V.step].length(), id="v-step-len"),
            rx.text(rx.cond(V.items[:: V.step].contains(4), "has4", "no4"), id="v-step-contains"),
            rx.text(V.items[V.a : V.b : V.step].to_string(), id="v-abs-str"),
            rx.text(rx.cond(V.left.deep_equals(cs_dict.value), "eq", "neq"), id="v-deq-cs"),
            rx.text(rx.cond(V.comp1.deep_equals(V.comp2), "eq", "neq"), id="v-deq-comp"),
            rx.text(rx.match(V.left.deep_equals(V.comp1), (True, "M-eq"), (False, "M-neq"), "M-default"), id="v-deq-match"),
            HookProbe.create(rx.text(rx.Var("hookProbeValue"), id="v-hook")),
        ]
    return rx.vstack(
        nav(),
        rx.heading("var ops"),
        rx.box(rx.foreach(V.items[-1::-1], _span), id="v-rev-foreach"),
        rx.box(rx.foreach(V.items[V.a : V.b], _span), id="v-ab-foreach"),
        rx.text(V.s[::-2], id="v-s-rev2"),
        rx.text(V.s[V.a : V.b], id="v-s-ab"),
        rx.text(V.emoji[::-1], id="v-emoji-rev"),
        rx.text(V.emoji.length(), id="v-emoji-len"),
        rx.text(V.items[V.a : V.b].to_string(), id="v-ab-str"),
        rx.text(V.d[V.key], id="v-objkey"),
        rx.box(rx.foreach(V.d, lambda kv: _span(kv[0] + "=" + kv[1].to_string())), id="v-dict-foreach"),
        rx.box(rx.foreach(V.d.items(), lambda kv: _span(kv[0] + ":" + kv[1].to_string())), id="v-dict-items"),
        rx.text(V.rows.pluck("name").join(","), id="v-pluck"),
        rx.text(V.rows.pluck("name").reverse().join(","), id="v-pluck-rev"),
        rx.text(V.items.reverse()[0:3].to_string(), id="v-rev-slice"),
        rx.text(V.left.to_string(), id="v-left"),
        rx.text(cs_dict.value.to_string(), id="v-csdict"),
        *alpha_only,
        rx.button("step=-3", on_click=V.set_step(-3), id="v-step-neg3"),
        rx.button("step=2", on_click=V.set_step(2), id="v-step-2"),
        rx.button("bounds 7,2", on_click=V.set_bounds(7, 2), id="v-bounds-72"),
        rx.button("bounds -8,-2", on_click=V.set_bounds(-8, -2), id="v-bounds-neg"),
        rx.button("bounds 2,7", on_click=V.set_bounds(2, 7), id="v-bounds-27"),
        rx.button("key=z", on_click=V.set_key("z"), id="v-key-z"),
        rx.button("key=missing", on_click=V.set_key("missing"), id="v-key-missing"),
        rx.button("mutate left", on_click=V.mutate_left, id="v-mutate-left"),
        rx.button("cs set", on_click=cs_dict.set_value({"a": [1, 2, 9], "b": [3]}), id="v-cs-set"),
        exc_panel(),
    )


# 6. type-check logging (#7353)
class TypeLogState(rx.State):
    n: int = 0
    nums: list[int] = [1]

    @rx.var
    def bad_inner(self) -> list[int]:
        return [f"s{self.n}"]

    @rx.var
    def bad_inner_const(self) -> list[int]:
        return ["const"]

    @rx.var
    def bad_outer(self) -> int:
        return f"x{self.n}"

    @rx.var(cache=False)
    def bad_uncached(self) -> list[int]:
        return ["u"]

    @rx.event
    def bump(self):
        self.n += 1

    @rx.event
    def assign_inner(self):
        self.nums = ["a"]

    @rx.event
    def assign_outer(self):
        self.nums = "notalist"

    @rx.event
    def mark(self, label: str):
        evlog(f"TYPELOG_MARK {label}")


def typelog_page() -> rx.Component:
    T = TypeLogState
    return rx.vstack(
        nav(),
        rx.heading("type-check logging"),
        rx.text(T.n, id="tl-n"),
        rx.text(T.bad_inner.to_string(), id="tl-bad-inner"),
        rx.text(T.bad_inner_const.to_string(), id="tl-bad-const"),
        rx.text(T.bad_outer.to_string(), id="tl-bad-outer"),
        rx.text(T.bad_uncached.to_string(), id="tl-bad-uncached"),
        rx.text(T.nums.to_string(), id="tl-nums"),
        rx.button("bump", on_click=T.bump, id="tl-bump"),
        rx.button("assign inner", on_click=T.assign_inner, id="tl-assign-inner"),
        rx.button("assign outer", on_click=T.assign_outer, id="tl-assign-outer"),
        rx.button("mark A", on_click=T.mark("A"), id="tl-mark-a"),
        rx.button("mark B", on_click=T.mark("B"), id="tl-mark-b"),
        rx.button("mark C", on_click=T.mark("C"), id="tl-mark-c"),
        rx.button("mark D", on_click=T.mark("D"), id="tl-mark-d"),
        exc_panel(),
    )


# 7. state API edge cases
class ApiSib2(rx.State):
    x: int = 10


class ApiSib1(rx.State):
    report: list[str] = []

    @rx.event(background=True)
    async def read_sibling(self):
        try:
            v_out = await self.get_var_value(ApiSib2.x)
        except Exception as e:
            v_out = type(e).__name__
        async with self:
            sib = await self.get_state(ApiSib2)
            v_in = sib.x
            sib.x += 1
            v_in2 = await self.get_var_value(ApiSib2.x)
            self.report.append(f"out={v_out} in={v_in} in2={v_in2}")
        try:
            v_after = await self.get_var_value(ApiSib2.x)
        except Exception as e:
            v_after = type(e).__name__
        async with self:
            self.report.append(f"after={v_after}")

    @rx.event
    def clear(self):
        self.report = []


class ApiSV(rx.State):
    pub: str = "pub0"
    _secret: str = "secret0"

    @rx.var
    def secret_view(self) -> str:
        return self._secret

    @rx.event
    def set_pub(self, v: str):
        self.pub = v


def raw_event_js(state_cls, handler: str, payload: dict) -> str:
    name = f"{state_cls.get_full_name()}.{handler}"
    return f"addEvents([ReflexEvent({json.dumps(name)}, {json.dumps(payload)})])"


class ResetState(rx.State):
    ls: str = rx.LocalStorage("ls-default", name="ev_ls")
    ck: str = rx.Cookie("ck-default", name="ev_ck")
    plain: str = "plain-default"

    @rx.event
    def mutate(self):
        self.ls = "ls-changed"
        self.ck = "ck-changed"
        self.plain = "plain-changed"

    @rx.event
    def do_reset(self):
        self.reset()


class ResetSub(ResetState):
    sub_val: str = "sub-default"

    @rx.event
    def mutate_sub(self):
        self.sub_val = "sub-changed"


class ResetCS(rx.ComponentState):
    cs_val: str = "cs-default"

    @rx.event
    def mutate_cs(self):
        self.cs_val = "cs-changed"

    @classmethod
    def get_component(cls, *children, **props) -> rx.Component:
        return rx.hstack(
            rx.button("mutate cs", on_click=cls.mutate_cs, id="reset-cs-mutate"),
            rx.text(cls.cs_val, id="reset-cs-val"),
        )


@dataclasses.dataclass
class Box:
    name: str = "box"
    items: list[int] = dataclasses.field(default_factory=list)
    nested: list[list[int]] = dataclasses.field(default_factory=lambda: [[1]])


class DcState(rx.State):
    box: Box = Box()
    snap: str = ""

    @rx.event
    def mutate(self):
        self.box.items.append(len(self.box.items))
        self.box.nested[0].append(7)

    @rx.event
    def snapshot(self):
        gv = self.get_value("box")
        dd = self.dict()[self.get_full_name()]["box_rx_state_"]
        self.snap = json.dumps({
            "gv_type": type(gv).__name__,
            "gv": dataclasses.asdict(gv) if dataclasses.is_dataclass(gv) else str(gv),
            "dict_type": type(dd).__name__,
            "dict": dataclasses.asdict(dd) if dataclasses.is_dataclass(dd) else dd,
        })


class UndeclState(rx.State):
    report: str = ""

    @rx.event
    def assign_undeclared(self):
        self.undeclared_attr = 42
        d = self.dict()
        self.report = (
            f"assigned in_dict={'undeclared_attr' in json.dumps(d, default=str)}"
            f" hasattr={hasattr(self, 'undeclared_attr')}"
        )

    @rx.event
    def read_back(self):
        self.report = f"readback={getattr(self, 'undeclared_attr', 'MISSING')}"


def api_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("state API"),
        rx.button("read sibling (bg)", on_click=ApiSib1.read_sibling, id="api-sib"),
        rx.text(ApiSib1.report.join(" ; "), id="api-sib-report"),
        rx.text(ApiSib2.x, id="api-sib2-x"),
        rx.text(ApiSV.pub, id="api-pub"),
        rx.text(ApiSV.secret_view, id="api-secret"),
        rx.button("setvar pub", on_click=rx.call_script(raw_event_js(ApiSV, "setvar", {"var_name": "pub", "value": "pub-raw"})), id="api-setvar-pub"),
        rx.button("setvar _secret", on_click=rx.call_script(raw_event_js(ApiSV, "setvar", {"var_name": "_secret", "value": "hacked"})), id="api-setvar-secret"),
        rx.button("setvar nonexistent", on_click=rx.call_script(raw_event_js(ApiSV, "setvar", {"var_name": "nonexistent", "value": "x"})), id="api-setvar-missing"),
        rx.button("setvar secret_view", on_click=rx.call_script(raw_event_js(ApiSV, "setvar", {"var_name": "secret_view", "value": "x"})), id="api-setvar-computed"),
        rx.button("setvar is_hydrated", on_click=rx.call_script(raw_event_js(ApiSV, "setvar", {"var_name": "is_hydrated", "value": False})), id="api-setvar-hydrated"),
        rx.button("raw nonexistent handler", on_click=rx.call_script(raw_event_js(ApiSV, "no_such_handler", {})), id="api-raw-missing-handler"),
        rx.text(ResetState.ls, id="reset-ls"),
        rx.text(ResetState.ck, id="reset-ck"),
        rx.text(ResetState.plain, id="reset-plain"),
        rx.text(ResetSub.sub_val, id="reset-sub"),
        ResetCS.create(),
        rx.button("mutate", on_click=[ResetState.mutate, ResetSub.mutate_sub], id="reset-mutate"),
        rx.button("reset", on_click=ResetState.do_reset, id="reset-do"),
        rx.text(DcState.box["items"].to_string(), id="dc-items"),
        rx.text(DcState.box["nested"].to_string(), id="dc-nested"),
        rx.text(DcState.snap, id="dc-snap"),
        rx.button("dc mutate", on_click=DcState.mutate, id="dc-mutate"),
        rx.button("dc snapshot", on_click=DcState.snapshot, id="dc-snapshot"),
        rx.button("assign undeclared", on_click=UndeclState.assign_undeclared, id="undecl-assign"),
        rx.button("read back", on_click=UndeclState.read_back, id="undecl-read"),
        rx.text(UndeclState.report, id="undecl-report"),
        exc_panel(),
    )


# 8. event handler binding (#7312)
class BindParent(rx.State):
    p_count: int = 0
    p_log: list[str] = []

    @rx.event
    def bump_parent(self):
        self.p_count += 1
        self.p_log.append(f"bump:self={type(self).__name__}")
        return BindParent.after_bump

    @rx.event
    def after_bump(self):
        self.p_log.append("after_bump")

    @rx.event
    def template_method(self):
        self.p_log.append(f"template:self={type(self).__name__}:kind={self._kind()}")

    def _kind(self) -> str:
        return "parent-kind"

    @rx.event
    def clear(self):
        self.p_log = []


class BindChild(BindParent):
    c_count: int = 0
    c_log: list[str] = []

    def _kind(self) -> str:
        return "child-kind"

    @rx.event
    def call_parent_via_self(self):
        self.c_count += 1
        return self.bump_parent()

    @rx.event
    def call_template_via_self(self):
        self.template_method()

    @rx.event(background=True)
    async def bg_call_parent(self):
        async with self:
            self.bump_parent()
        try:
            self.bump_parent()
            res = "no-error"
        except Exception as e:
            res = type(e).__name__
        async with self:
            self.c_log.append(f"bg_outside={res}")


class BindOther(rx.State):
    items: list[str] = ["i0", "i1"]


class BindArgs(rx.State):
    got: list[str] = []

    @rx.event
    def take0(self):
        self.got.append("take0")

    @rx.event
    def take1(self, a: str):
        self.got.append(f"take1:{a}")

    @rx.event
    def take2(self, a: str, b: int):
        self.got.append(f"take2:{a}:{b}:{type(b).__name__}")

    @rx.event
    def take3(self, a: str, b: int, c: str):
        self.got.append(f"take3:{a}:{b}:{c}")

    @rx.event
    def take4(self, a: str, b: int, c: str, d: int):
        self.got.append(f"take4:{a}:{b}:{c}:{d}")

    @rx.event
    def take5(self, a: str, b: int, c: str, d: int, e: str):
        self.got.append(f"take5:{a}:{b}:{c}:{d}:{e}")

    @rx.event
    def clear(self):
        self.got = []


def bind_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("handler binding"),
        rx.button("clear", on_click=[BindParent.clear, BindArgs.clear], id="bind-clear"),
        rx.button("child.template_method (inherited)", on_click=BindChild.template_method, id="bind-inherited-template"),
        rx.button("child.call_template_via_self", on_click=BindChild.call_template_via_self, id="bind-template-via-self"),
        rx.button("child.call_parent_via_self", on_click=BindChild.call_parent_via_self, id="bind-parent-via-self"),
        rx.button("child.bg_call_parent", on_click=BindChild.bg_call_parent, id="bind-bg-parent"),
        rx.text(BindParent.p_count, id="bind-p-count"),
        rx.text(BindChild.c_count, id="bind-c-count"),
        rx.text(BindParent.p_log.join(" ; "), id="bind-p-log"),
        rx.text(BindChild.c_log.join(" ; "), id="bind-c-log"),
        rx.foreach(
            BindOther.items,
            lambda item, idx: rx.hstack(
                rx.button("0", on_click=BindArgs.take0, id="bind-take0-" + idx.to_string()),
                rx.button("1", on_click=BindArgs.take1(item), id="bind-take1-" + idx.to_string()),
                rx.button("2", on_click=BindArgs.take2(item, idx), id="bind-take2-" + idx.to_string()),
                rx.button("3", on_click=BindArgs.take3(item, idx, item), id="bind-take3-" + idx.to_string()),
                rx.button("4", on_click=BindArgs.take4(item, idx, item, idx), id="bind-take4-" + idx.to_string()),
                rx.button("5", on_click=BindArgs.take5(item, idx, item, idx, "five"), id="bind-take5-" + idx.to_string()),
            ),
        ),
        rx.button("lambda", on_click=lambda: BindArgs.take1("lam"), id="bind-lambda"),
        rx.button("rx.event(lambda)", on_click=rx.event(lambda: BindArgs.take1("rxlam")), id="bind-rxevent-lambda"),
        rx.input(id="bind-lambda-input", on_blur=lambda v: BindArgs.take2(v, 5)),
        rx.text(BindArgs.got.join(" ; "), id="bind-got"),
        exc_panel(),
    )


# 9. #7465 double-underscore (private) attributes used inside event handlers
class PrivMixin(rx.State, mixin=True):
    __MIX_LIMIT = 2
    mix_out: str = ""

    @rx.event
    def mix_scratch(self, v: str):
        self.__scratch = v
        self.mix_out = f"scratch={self.__scratch} limit={self.__MIX_LIMIT}"

    @rx.event
    def mix_read(self):
        self.mix_out = f"read={getattr(self, '_PrivMixin__scratch', 'MISSING')}"


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

    @rx.event
    def read_private(self):
        self.note = f"readback last={getattr(self, '_PrivA__last_seen', 'unset')}"

    @rx.var
    def view_private(self) -> str:
        return f"view last={getattr(self, '_PrivA__last_seen', 'unset')}"


class PrivB(PrivMixin, rx.State):
    """Second consumer of the mixin: its private scratch must stay independent."""


PRIV_FIELD_HANDLERS = []
if IS_ALPHA:

    class PrivF(rx.State):
        """0.10.0a2 feature: an explicit rx.field() makes a dunder a backend var."""

        __counter: rx.Field[int] = rx.field(0)

        @rx.event
        def inc(self):
            self.__counter += 1

        @rx.var
        def counter_view(self) -> int:
            return self.__counter

    PRIV_FIELD_HANDLERS = [
        rx.button("field inc", on_click=PrivF.inc, id="privf-inc"),
        rx.text(PrivF.counter_view, id="privf-view"),
    ]


def priv_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("private attributes"),
        rx.button("bump", on_click=PrivA.bump, id="priv-bump"),
        rx.button("private only", on_click=PrivA.private_only("P"), id="priv-only"),
        rx.button("read private", on_click=PrivA.read_private, id="priv-read"),
        rx.text(PrivA.count, id="priv-count"),
        rx.text(PrivA.note, id="priv-note"),
        rx.text(PrivA.view_private, id="priv-view"),
        rx.button("mixA scratch", on_click=PrivA.mix_scratch("SA"), id="priv-mixa"),
        rx.button("mixB scratch", on_click=PrivB.mix_scratch("SB"), id="priv-mixb"),
        rx.button("mixA read", on_click=PrivA.mix_read, id="priv-mixa-read"),
        rx.button("mixB read", on_click=PrivB.mix_read, id="priv-mixb-read"),
        rx.text(PrivA.mix_out, id="priv-mixa-out"),
        rx.text(PrivB.mix_out, id="priv-mixb-out"),
        *PRIV_FIELD_HANDLERS,
        exc_panel(),
    )


def index() -> rx.Component:
    return rx.vstack(nav(), rx.heading("events_vars"), rx.text(SupState.router.session.client_token, id="token"))


app = rx.App(
    backend_exception_handler=ev_backend_exc,
    frontend_exception_handler=ev_frontend_exc,
)
app.add_page(index)
app.add_page(sup_page, route="/sup")
app.add_page(deco_page, route="/deco")
app.add_page(nested_page, route="/nested")
app.add_page(throttle_page, route="/throttle")
app.add_page(vars_page, route="/vars")
app.add_page(typelog_page, route="/typelog")
app.add_page(api_page, route="/api")
app.add_page(bind_page, route="/bind")
app.add_page(priv_page, route="/priv")
