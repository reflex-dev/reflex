"""Minimal repros for the events cluster (default rx.App() exception handler on purpose).

1. Side lead: a chained handler raises (A returns/yields B, B raises after mutating state).
   When does the partial state reach the browser: with the error toast, or with the NEXT event?
   Same for a single handler that mutates then raises, and for an on_load handler that does.
2. supersedes: a superseded (cancelled) handler's mutation made after its last yield.
"""

import asyncio
import importlib.metadata
import time

import reflex as rx

# venv guard (a3_events_tp): bin/start.sh exports EV_EXPECT_VENV=<venv name>
_EXPECT_VENV = __import__("os").environ.get("EV_EXPECT_VENV", "")
assert _EXPECT_VENV and f"/scratchpad/envs/{_EXPECT_VENV}/" in rx.__file__, (rx.__file__, _EXPECT_VENV)
print(f"VENV_GUARD ok venv={_EXPECT_VENV} reflex={rx.__file__}", flush=True)

VERSION = importlib.metadata.version("reflex")


def mark(msg: str) -> None:
    print(f"MINI {time.time():.3f} {msg}", flush=True)


class ChainState(rx.State):
    status: str = "idle"
    items: list[str] = []
    pings: int = 0
    load_note: str = "none"

    @rx.event
    def a_returns_b(self):
        self.status = "A-set"
        mark("a_returns_b")
        return ChainState.b_raises

    @rx.event
    def a_yields_b(self):
        self.status = "AY-set"
        mark("a_yields_b")
        yield ChainState.b_raises

    @rx.event
    def b_raises(self):
        self.items.append("B-partial")
        mark("b_raises (raising)")
        raise RuntimeError("B-intentional")

    @rx.event
    def direct_raises(self):
        self.status = "direct-partial"
        mark("direct_raises (raising)")
        raise RuntimeError("direct-intentional")

    @rx.event
    async def async_raises(self):
        self.status = "async-partial"
        mark("async_raises (raising)")
        raise RuntimeError("async-intentional")

    @rx.event
    def gen_yield_then_raise(self):
        self.status = "gen-flushed"
        yield
        self.items.append("gen-partial")
        mark("gen_yield_then_raise (raising)")
        raise RuntimeError("gen-intentional")

    @rx.event(background=True)
    async def bg_raise_inside(self):
        async with self:
            self.status = "bg-inside-partial"
            mark("bg_raise_inside (raising inside async with self)")
            raise RuntimeError("bg-inside-intentional")

    @rx.event(background=True)
    async def bg_raise_after(self):
        async with self:
            self.status = "bg-before-raise"
        mark("bg_raise_after (raising outside the lock)")
        raise RuntimeError("bg-after-intentional")

    @rx.event
    def ping(self):
        self.pings += 1
        mark(f"ping {self.pings}")

    @rx.event
    def onload_raises(self):
        self.load_note = "onload-partial"
        mark("onload_raises (raising)")
        raise RuntimeError("onload-intentional")

    @rx.event
    def reset_all(self):
        self.status = "idle"
        self.items = []
        self.load_note = "none"


class SupMini(rx.State):
    log: list[str] = []
    other: str = "none"

    @rx.event(supersedes=True)
    async def work(self, label: str):
        self.log.append(f"{label}:start")
        yield
        self.log.append(f"{label}:after-yield")
        mark(f"work {label} sleeping")
        await asyncio.sleep(3)
        self.log.append(f"{label}:end")
        mark(f"work {label} done")

    @rx.event(supersedes=True)
    async def work_split(self, label: str):
        """Variant: the superseding call (label b) never touches `log`."""
        if label == "b":
            self.other = "b-ran"
            mark("work_split b ran (no log change)")
            return
        self.log.append(f"{label}:start")
        yield
        self.log.append(f"{label}:after-yield")
        mark(f"work_split {label} sleeping")
        await asyncio.sleep(3)
        self.log.append(f"{label}:end")
        mark(f"work_split {label} done")

    @rx.event
    def clear(self):
        self.log = []
        self.other = "none"


class PrivCS(rx.ComponentState):
    """#7465 in a ComponentState: create() makes a dynamic subclass; the mangled names belong to PrivCS."""

    __STEP = 2
    count: int = 0
    note: str = ""

    @rx.event
    def bump(self):
        self.count += self.__STEP
        self.__last = self.count
        self.note = f"count={self.count} last={self.__last}"

    @classmethod
    def get_component(cls, *children, **props) -> rx.Component:
        name = props.pop("name", "x")
        return rx.hstack(
            rx.button(f"pcs-{name}", on_click=cls.bump, id=f"pcs-{name}"),
            rx.text(cls.note, id=f"pcs-note-{name}"),
        )


class PrivBg(rx.State):
    """#7465 in a background task: private plain attributes outside / inside `async with self`."""

    out: str = ""

    @rx.event(background=True)
    async def bg_private(self):
        try:
            self.__outside = 1
            res = "outside=ok"
        except Exception as e:  # noqa: BLE001
            res = f"outside={type(e).__name__}"
        async with self:
            self.__inside = 2
            self.out = f"{res} inside={self.__inside}"


class EmojiState(rx.State):
    emoji: str = "a\U0001f600b"


def panel() -> rx.Component:
    return rx.vstack(
        rx.text(VERSION, id="version"),
        rx.text(ChainState.status, id="status"),
        rx.text(ChainState.items.join(","), id="items"),
        rx.text(ChainState.pings, id="pings"),
        rx.text(ChainState.load_note, id="load-note"),
        rx.hstack(
            rx.button("A returns B", on_click=ChainState.a_returns_b, id="a-ret"),
            rx.button("A yields B", on_click=ChainState.a_yields_b, id="a-yield"),
            rx.button("direct raise", on_click=ChainState.direct_raises, id="direct"),
            rx.button("async raise", on_click=ChainState.async_raises, id="async"),
            rx.button("gen yield then raise", on_click=ChainState.gen_yield_then_raise, id="gen"),
            rx.button("bg raise inside", on_click=ChainState.bg_raise_inside, id="bg-inside"),
            rx.button("bg raise after", on_click=ChainState.bg_raise_after, id="bg-after"),
            rx.button("ping", on_click=ChainState.ping, id="ping"),
            rx.button("reset", on_click=ChainState.reset_all, id="reset"),
        ),
        rx.hstack(
            rx.button("work a", on_click=SupMini.work("a"), id="work-a"),
            rx.button("work b", on_click=SupMini.work("b"), id="work-b"),
            rx.button("sup clear", on_click=SupMini.clear, id="sup-clear"),
            rx.button("split a", on_click=SupMini.work_split("a"), id="split-a"),
            rx.button("split b", on_click=SupMini.work_split("b"), id="split-b"),
            rx.text(SupMini.log.join(","), id="sup-log"),
            rx.text(SupMini.other, id="sup-other"),
        ),
        rx.link("to onload page", href="/onload", id="to-onload"),
    )


def index() -> rx.Component:
    return panel()


def onload_page() -> rx.Component:
    return panel()


def emoji_rev() -> rx.Component:
    """Only the reversed emoji string (JS reversal splits the surrogate pair)."""
    return rx.vstack(rx.text(VERSION, id="version"), rx.text(EmojiState.emoji[::-1], id="emoji-rev"))


def emoji_len() -> rx.Component:
    return rx.vstack(rx.text(VERSION, id="version"), rx.text(EmojiState.emoji.length(), id="emoji-len"))


def emoji_plain() -> rx.Component:
    return rx.vstack(rx.text(VERSION, id="version"), rx.text(EmojiState.emoji, id="emoji-plain"))


def priv2() -> rx.Component:
    return rx.vstack(
        rx.text(VERSION, id="version"),
        PrivCS.create(name="A"),
        PrivCS.create(name="B"),
        rx.button("bg private", on_click=PrivBg.bg_private, id="pbg"),
        rx.text(PrivBg.out, id="pbg-out"),
        rx.text(ChainState.pings, id="pings"),
        rx.button("ping", on_click=ChainState.ping, id="ping"),
    )


app = rx.App()
app.add_page(index)
app.add_page(onload_page, route="/onload", on_load=ChainState.onload_raises)
app.add_page(emoji_rev, route="/emoji-rev")
app.add_page(emoji_len, route="/emoji-len")
app.add_page(emoji_plain, route="/emoji-plain")
app.add_page(priv2, route="/priv2")
