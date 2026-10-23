"""App A for the state-events cluster: on_load sequences, cancellation, dict mutation,
async uncached vars, memo identity, streaming + background races, unknown substate."""

import asyncio
import os
import time
from pathlib import Path

import reflex as rx
from reflex.event import EventSpec
try:
    from reflex_base.event import event_sequence
except ImportError:  # 0.10.0 baseline
    def event_sequence(events):
        return events if isinstance(events, (list, tuple)) else [events]

MARKERS = Path(__file__).resolve().parent.parent / "markers"
MARKERS.mkdir(exist_ok=True)


def mark(name: str) -> None:
    """Append a timestamped marker line to markers/<name>."""
    with (MARKERS / name).open("a") as f:
        f.write(f"{time.time():.3f}\n")


class A(rx.State):
    a_log: list[str] = []
    counter: int = 0

    @rx.event
    def h1(self):
        self.a_log.append("A.h1")

    @rx.event
    def load_tuple_a(self):
        self.a_log.append("A.load_tuple_a")

    @rx.event
    def load_list_a(self):
        self.a_log.append("A.load_list_a")

    @rx.event
    def load_single(self):
        self.a_log.append("A.load_single")

    @rx.event
    def clear(self):
        self.a_log = []
        self.counter = 0

    @rx.event
    def returns_tuple(self):
        """Handler returning a tuple of events (not a list)."""
        self.a_log.append("A.returns_tuple")
        return [A.h1, B.h2]  # 0.10.0 baseline: tuples rejected

    @rx.event
    def returns_typed_list(self):
        """Handler returning a var typed list[EventSpec] built dynamically."""
        self.a_log.append("A.returns_typed_list")
        events: list[EventSpec] = []
        for _ in range(2):
            events.append(A.h1())
        events.append(B.h2())
        return events

    @rx.event
    def returns_event_sequence_single(self):
        self.a_log.append("A.returns_event_sequence_single")
        return event_sequence(B.h2())

    @rx.event
    def returns_event_sequence_tuple(self):
        self.a_log.append("A.returns_event_sequence_tuple")
        return event_sequence((A.h1(), B.h2(), A.h1()))

    @rx.event
    def returns_generator_tuple(self):
        self.a_log.append("A.returns_generator_tuple")
        yield [A.h1, B.h2]
        self.counter += 1
        yield [B.h2()]

    @rx.event
    def noop(self):
        """Changes nothing: used by the memo identity test."""
        mark("noop")

    @rx.event
    def bump_counter(self):
        self.counter += 1


class B(rx.State):
    b_log: list[str] = []

    @rx.event
    def h2(self):
        self.b_log.append("B.h2")

    @rx.event
    def load_tuple_b(self):
        self.b_log.append("B.load_tuple_b")

    @rx.event
    def load_list_b(self):
        self.b_log.append("B.load_list_b")

    @rx.event
    def clear(self):
        self.b_log = []


def on_load_typed() -> list[EventSpec]:
    events: list[EventSpec] = [A.load_tuple_a(), B.load_tuple_b()]
    return events


class Slow(rx.State):
    """Slow on_load chain, with markers, to prove cancellation on disconnect."""

    progress: str = "none"
    bg_result: str = ""

    @rx.event
    async def s1(self):
        mark("s1_start")
        await asyncio.sleep(1.7)
        mark("s1_done")
        self.progress = "s1"
        return Slow.s2

    @rx.event
    async def s2(self):
        mark("s2_start")
        await asyncio.sleep(1.7)
        mark("s2_done")
        self.progress = "s2"
        yield Slow.s3

    @rx.event
    async def s3(self):
        mark("s3_start")
        await asyncio.sleep(1.7)
        mark("s3_done")
        self.progress = "s3-finished"

    @rx.event(background=True)
    async def bg(self):
        mark("bg_start")
        await asyncio.sleep(5.5)
        async with self:
            self.bg_result = "bg finished"
        mark("bg_done")

    @rx.event
    def reset_all(self):
        self.progress = "none"
        self.bg_result = ""


class DictState(rx.State):
    data: dict[str, dict[str, int]] = {
        "alpha": {"x": 1, "y": 2},
        "beta": {"x": 10, "y": 20},
    }

    @rx.var
    def total(self) -> int:
        return sum(sum(inner.values()) for inner in self.data.values())

    @rx.var
    def alpha_x(self) -> int:
        return self.data["alpha"]["x"]

    @rx.event
    def bump_via_values(self):
        for inner in self.data.values():
            inner["x"] += 1

    @rx.event
    def bump_via_items(self):
        for key, inner in self.data.items():
            inner["y"] += 100 if key == "alpha" else 1

    @rx.event
    def add_key_via_values(self):
        for inner in self.data.values():
            inner["z"] = inner.get("z", 0) + 7

    @rx.event
    def bump_via_list_values(self):
        """list(self.data.values()) then mutate: also expected to be tracked."""
        for inner in list(self.data.values()):
            inner["x"] += 1000

    @rx.event
    def reset_all(self):
        self.data = {"alpha": {"x": 1, "y": 2}, "beta": {"x": 10, "y": 20}}


class AsyncVarState(rx.State):
    """Async uncached computed var only referenced on /page2."""

    seed: int = 0
    async_calls: int = 0

    @rx.var(cache=False)
    async def slow_doubled(self) -> int:
        await asyncio.sleep(0.01)
        return self.seed * 2

    @rx.event
    def bump_seed(self):
        self.seed += 1


class MemoState(rx.State):
    items: list[str] = ["one", "two", "three"]
    meta: dict[str, int] = {"a": 1, "b": 2}
    unrelated: int = 0

    @rx.event
    def noop(self):
        mark("memo_noop")

    @rx.event
    def bump_unrelated(self):
        self.unrelated += 1

    @rx.event
    def set_same_items(self):
        """Assign an equal-but-new list: value-identical update."""
        self.items = list(self.items)

    @rx.event
    def append_item(self):
        self.items.append(f"item{len(self.items)}")

    @rx.event
    def bump_meta(self):
        self.meta["a"] += 1


class RenderProbe(rx.Fragment):
    """Fragment whose hook increments window.__renders[name] on every render."""

    _probe_name: str = ""

    @classmethod
    def create(cls, *children, probe_name: str = "", **props):
        comp = super().create(*children, **props)
        comp._probe_name = probe_name
        return comp

    def add_hooks(self):
        n = self._probe_name
        return [
            f'if (typeof window !== "undefined") {{ window.__renders = window.__renders || {{}}; window.__renders["{n}"] = (window.__renders["{n}"] || 0) + 1; }}'
        ]


@rx.memo
def memo_child(items: rx.Var[list[str]], meta: rx.Var[dict[str, int]]) -> rx.Component:
    return rx.box(
        RenderProbe.create(probe_name="memo_child"),
        rx.text("memo items: ", items.join(",")),
        rx.text("memo meta a=", meta["a"].to_string()),
        id="memo-child",
    )


@rx.memo
def memo_scalar(unrelated: rx.Var[int]) -> rx.Component:
    return rx.box(
        RenderProbe.create(probe_name="memo_scalar"),
        rx.text("unrelated=", unrelated),
        id="memo-scalar",
    )


class StreamState(rx.State):
    ticks: int = 0
    shared: int = 0
    stream_log: list[str] = []
    bg_running: bool = False

    @rx.event
    async def stream(self):
        for i in range(25):
            self.ticks = i + 1
            self.shared += 1
            mark("stream_tick")
            yield
            await asyncio.sleep(0.25)
        mark("stream_done")

    @rx.event(background=True)
    async def bg_race(self):
        async with self:
            self.bg_running = True
        for _ in range(30):
            await asyncio.sleep(0.2)
            async with self:
                self.shared += 10
            mark("bg_race_tick")
        async with self:
            self.bg_running = False
        mark("bg_race_done")

    @rx.event
    def reset_all(self):
        self.ticks = 0
        self.shared = 0
        self.bg_running = False


if os.environ.get("EXTRA_SUBSTATE"):

    class Hidden(rx.State):
        """Only exists in the backend when EXTRA_SUBSTATE is set."""

        hidden_count: int = 0

        @rx.event
        def bump(self):
            self.hidden_count += 1

    class HiddenCaller(rx.State):
        @rx.event
        def call_hidden(self):
            return Hidden.bump

else:

    class HiddenCaller(rx.State):
        @rx.event
        def call_hidden(self):
            pass


def nav() -> rx.Component:
    return rx.hstack(
        rx.link("index", href="/"),
        rx.link("list", href="/list"),
        rx.link("single", href="/single"),
        rx.link("typed", href="/typed"),
        rx.link("slow", href="/slow"),
        rx.link("dict", href="/dict"),
        rx.link("page2", href="/page2"),
        rx.link("memo", href="/memo"),
        rx.link("stream", href="/stream"),
        rx.link("blank", href="/blank"),
        spacing="3",
    )


def logs() -> rx.Component:
    return rx.vstack(
        rx.text("A.log: ", A.a_log.join("|"), id="a-log"),
        rx.text("B.log: ", B.b_log.join("|"), id="b-log"),
        rx.text("counter: ", A.counter, id="counter"),
        rx.button("clear", on_click=[A.clear, B.clear], id="clear"),
    )


def index() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("index: on_load tuple"),
        logs(),
        rx.button("tuple click", on_click=[A.h1, B.h2], id="btn-tuple"),
        rx.button("returns tuple", on_click=A.returns_tuple, id="btn-rt"),
        rx.button("returns typed list", on_click=A.returns_typed_list, id="btn-rtl"),
        rx.button("event_sequence single", on_click=A.returns_event_sequence_single, id="btn-es1"),
        rx.button("event_sequence tuple", on_click=A.returns_event_sequence_tuple, id="btn-est"),
        rx.button("generator tuple", on_click=A.returns_generator_tuple, id="btn-gen"),
        rx.button("bump seed (async var only on page2)", on_click=AsyncVarState.bump_seed, id="btn-seed"),
        rx.text("seed: ", AsyncVarState.seed, id="seed"),
        rx.button("call hidden", on_click=HiddenCaller.call_hidden, id="btn-hidden"),
        rx.button("bump counter", on_click=A.bump_counter, id="btn-counter"),
    )


def list_page() -> rx.Component:
    return rx.vstack(nav(), rx.heading("list: on_load list"), logs())


def single_page() -> rx.Component:
    return rx.vstack(nav(), rx.heading("single: on_load single"), logs())


def typed_page() -> rx.Component:
    return rx.vstack(nav(), rx.heading("typed: on_load list[EventSpec] var"), logs())


def slow_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("slow on_load chain"),
        rx.text("progress: ", Slow.progress, id="progress"),
        rx.text("bg: ", Slow.bg_result, id="bg"),
        rx.button("reset", on_click=Slow.reset_all, id="reset"),
    )


def dict_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("dict mutation via values()/items()"),
        rx.text("total: ", DictState.total, id="total"),
        rx.text("alpha_x: ", DictState.alpha_x, id="alpha-x"),
        rx.text("alpha.y: ", DictState.data["alpha"]["y"], id="alpha-y"),
        rx.text("data: ", DictState.data.to_string(), id="data"),
        rx.button("bump via values", on_click=DictState.bump_via_values, id="btn-values"),
        rx.button("bump via items", on_click=DictState.bump_via_items, id="btn-items"),
        rx.button("add key via values", on_click=DictState.add_key_via_values, id="btn-addkey"),
        rx.button("bump via list(values)", on_click=DictState.bump_via_list_values, id="btn-listvalues"),
        rx.button("reset", on_click=DictState.reset_all, id="btn-reset"),
    )


def page2() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("page2: async uncached var"),
        rx.text("seed: ", AsyncVarState.seed, id="seed"),
        rx.text("doubled: ", AsyncVarState.slow_doubled, id="doubled"),
        rx.button("bump seed", on_click=AsyncVarState.bump_seed, id="btn-seed"),
    )


def memo_page() -> rx.Component:
    return rx.vstack(
        nav(),
        RenderProbe.create(probe_name="memo_page"),
        rx.heading("memo identity"),
        memo_child(items=MemoState.items, meta=MemoState.meta),
        memo_scalar(unrelated=MemoState.unrelated),
        rx.text("unrelated: ", MemoState.unrelated, id="unrelated"),
        rx.button("noop", on_click=MemoState.noop, id="btn-noop"),
        rx.button("bump unrelated", on_click=MemoState.bump_unrelated, id="btn-unrelated"),
        rx.button("set same items", on_click=MemoState.set_same_items, id="btn-same"),
        rx.button("append item", on_click=MemoState.append_item, id="btn-append"),
        rx.button("bump meta", on_click=MemoState.bump_meta, id="btn-meta"),
    )


def stream_page() -> rx.Component:
    return rx.vstack(
        nav(),
        rx.heading("stream + background race"),
        rx.text("ticks: ", StreamState.ticks, id="ticks"),
        rx.text("shared: ", StreamState.shared, id="shared"),
        rx.text("bg_running: ", StreamState.bg_running.to_string(), id="bg-running"),
        rx.button("start both", on_click=[StreamState.bg_race, StreamState.stream], id="btn-both"),
        rx.button("stream only", on_click=StreamState.stream, id="btn-stream"),
        rx.button("reset", on_click=StreamState.reset_all, id="btn-reset"),
    )


def blank() -> rx.Component:
    return rx.vstack(nav(), rx.heading("blank page, no on_load"), rx.text("blank", id="blank"))


app = rx.App()
app.add_page(index, route="/", on_load=[A.load_tuple_a, B.load_tuple_b])
app.add_page(list_page, route="/list", on_load=[A.load_list_a, B.load_list_b])
app.add_page(single_page, route="/single", on_load=A.load_single)
app.add_page(typed_page, route="/typed", on_load=on_load_typed())
app.add_page(slow_page, route="/slow", on_load=[Slow.bg, Slow.s1])
app.add_page(dict_page, route="/dict")
app.add_page(page2, route="/page2")
app.add_page(memo_page, route="/memo")
app.add_page(stream_page, route="/stream")
app.add_page(blank, route="/blank")
