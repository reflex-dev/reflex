"""Decorator stacking + failure paths. Runs unchanged on reflex 0.10.1 and 0.11.0a1."""

import asyncio
import functools
import json
import os
import time

import reflex as rx
from reflex.event import Event
from reflex.state import StateUpdate, _override_base_method

MW_LOG = os.environ.get("AWAIT_MW_LOG", "mw_events.jsonl")
IMPORT_RESULTS: dict[str, str] = {}


def _try(label: str, fn):
    try:
        IMPORT_RESULTS[label] = repr(fn())
    except Exception as ex:
        IMPORT_RESULTS[label] = f"!{type(ex).__name__}: {str(ex)[:120]}"


def logged(fn):
    """A sync functools.wraps decorator (logging/timing style)."""

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        self.calls = [*self.calls, f"logged:{wrapper.__name__}"]
        return fn(self, *args, **kwargs)

    return wrapper


def alogged(fn):
    """An async functools.wraps decorator."""

    @functools.wraps(fn)
    async def wrapper(self, *args, **kwargs):
        self.calls = [*self.calls, f"alogged:{wrapper.__name__}"]
        return await fn(self, *args, **kwargs)

    return wrapper


class PlainMixin:
    """A plain python mixin (not a state)."""

    @rx.event
    def mix_plain(self):
        self.out = "mix_plain"


class Helper:
    """Not a state at all."""

    @rx.event
    def compute(self, x):
        return x * 3

    @rx.event
    @staticmethod
    def static_under_event(x):
        return x * 2

    @staticmethod
    @rx.event
    def static_over_event(x):
        return x * 2

    @rx.event
    @classmethod
    def class_under_event(cls, x):
        return f"{cls.__name__}:{x}"


class D(PlainMixin, rx.State):
    out: str = ""
    n: int = 0
    calls: list[str] = []

    @rx.var
    def summary(self) -> str:
        # a handler used as a helper from a computed var
        return self.fmt(self.n)

    @rx.event
    def fmt(self, n: int) -> str:
        return f"n={n}"

    @rx.event
    def reset_d(self):
        self.reset()
        self.out = "reset"

    @rx.event
    def plain(self):
        self.out = "plain"

    def undecorated(self):
        self.out = "undecorated"

    @rx.event
    @logged
    def below(self):
        self.out = "below"

    @logged
    @rx.event
    def above(self):
        self.out = "above"

    @logged
    @rx.event
    def above_args(self, v: int, w: str = "d"):
        self.out = f"above_args {v!r} {w!r}"

    @alogged
    @rx.event
    async def above_async(self):
        self.out = "above_async"

    @rx.event
    @alogged
    async def below_async(self):
        self.out = "below_async"

    @logged
    @rx.event
    def above_gen(self):
        self.out = "above_gen 1"
        yield
        self.out = "above_gen 2"

    @rx.event(background=True)
    @alogged
    async def bg_below(self):
        async with self:
            self.out = "bg_below"

    @rx.event
    def uses_helpers(self):
        res = []
        for label, fn in (
            ("self.fmt", lambda: self.fmt(7)),
            ("self.above_args", lambda: self.above_args(1, "x")),
            ("self.below", lambda: self.below()),
            ("static_over", lambda: D.static_over(4)),
            ("self.static_over", lambda: self.static_over(4)),
            ("static_under", lambda: D.static_under(4)),
            ("class_under", lambda: D.class_under(4)),
            ("Helper().compute", lambda: Helper().compute(3)),
        ):
            try:
                res.append(f"{label}={fn()!r}")
            except Exception as ex:
                res.append(f"{label}!{type(ex).__name__}:{str(ex)[:60]}")
        self.out = "uses_helpers: " + " | ".join(res)

    @staticmethod
    @rx.event
    def static_over(x):
        return x * 2

    @rx.event
    @staticmethod
    def static_under(x):
        return x * 2

    @rx.event
    @classmethod
    def class_under(cls, x):
        return f"{cls.__name__}:{x}"


@rx.event
def helper_fn(x: int) -> int:
    """A module-level helper wrongly decorated."""
    return x + 1


@rx.event
def decentralized(state: D, v: int):
    state.out = f"decentralized {v}"


@rx.event
def decentralized_str(state: "D", v: int):
    state.out = f"decentralized_str {v}"


_try("helper_fn(1)", lambda: helper_fn(1))
_try("type(helper_fn)", lambda: type(helper_fn).__name__)
_try("Helper().compute(3)", lambda: Helper().compute(3))
_try("Helper.compute(Helper(), 3)", lambda: Helper.compute(Helper(), 3))
_try("Helper.static_under_event(3)", lambda: Helper.static_under_event(3))
_try("Helper.static_over_event(3)", lambda: Helper.static_over_event(3))
_try("Helper.class_under_event(3)", lambda: Helper.class_under_event(3))
_try("D.static_over(3)", lambda: D.static_over(3))
_try("D.static_under(3)", lambda: D.static_under(3))
_try("type(D.plain)", lambda: type(D.plain).__name__)
_try("type(D.above)", lambda: type(D.above).__name__)
_try("type(D.__dict__['above'])", lambda: type(D.__dict__["above"]).__name__)
_try("D.above.__wrapped__", lambda: type(D.above.__wrapped__).__name__)
_try("D.plain.__name__", lambda: D.plain.__name__)
_try("D.plain.__doc__", lambda: D.plain.__doc__)
_try("D.event_handlers", lambda: sorted(D.event_handlers))
_try("D.above_gen.fn", lambda: type(D.event_handlers["above_gen"].fn).__name__)


DOUBLE: dict[str, type] = {}


def _define_double(label: str, make):
    """One state class per double-@rx.event pattern; 0.11.0a1 fails to create some of them."""
    try:
        DOUBLE[label] = make()
        eh = DOUBLE[label].event_handlers["h"]
        IMPORT_RESULTS[f"define {label}"] = f"ok bg={eh.is_background} actions={eh.event_actions}"
    except Exception as ex:
        IMPORT_RESULTS[f"define {label}"] = f"!{type(ex).__name__}: {ex}"


def _double_plain():
    class DoublePlain(rx.State):
        out: str = ""

        @rx.event
        @rx.event
        def h(self):
            self.out = "double_plain"

    return DoublePlain


def _double_bg():
    class DoubleBg(rx.State):
        out: str = ""

        @rx.event
        @rx.event(background=True)
        async def h(self):
            # reflex-examples overkey/overkey.py:164
            await asyncio.sleep(0.1)
            async with self:
                self.out = "double_bg"

    return DoubleBg


def _double_bg_rev():
    class DoubleBgRev(rx.State):
        out: str = ""

        @rx.event(background=True)
        @rx.event
        async def h(self):
            await asyncio.sleep(0.1)
            async with self:
                self.out = "double_bg_rev"

    return DoubleBgRev


def _double_throttle():
    class DoubleThrottle(rx.State):
        out: str = ""

        @rx.event
        @rx.event(throttle=300)
        def h(self):
            self.out = "double_throttle"

    return DoubleThrottle


def _double_throttle_rev():
    class DoubleThrottleRev(rx.State):
        out: str = ""

        @rx.event(throttle=300)
        @rx.event
        def h(self):
            self.out = "double_throttle_rev"

    return DoubleThrottleRev


_define_double("double_plain", _double_plain)
_define_double("double_bg", _double_bg)
_define_double("double_bg_rev", _double_bg_rev)
_define_double("double_throttle", _double_throttle)
_define_double("double_throttle_rev", _double_throttle_rev)


class Other(rx.State):
    n: int = 0


class F(rx.State):
    a: int = 0
    b: int = 0
    c: int = 0
    status: str = ""
    count: int = 0
    partial_log: list[str] = []
    done_log: list[str] = []
    bg_status: str = ""
    load_mode: str = ""
    result: str = ""
    gated_runs: int = 0

    @rx.var
    def b_times_ten(self) -> int:
        return self.b * 10

    @_override_base_method
    async def get_state(self, state_cls):
        """Test hook: make loading `Other` slow or failing (stands in for a slow/broken store)."""
        if state_cls is Other and self.load_mode:
            mode, self.load_mode = self.load_mode, ""
            print(f"HOOK get_state(Other) mode={mode} t={time.time():.3f}", flush=True)
            if mode == "fail":
                msg = "simulated load failure"
                raise RuntimeError(msg)
            await asyncio.sleep(30)
        return await super().get_state(state_cls)

    @rx.event
    def reset_f(self):
        self.reset()
        self.result = "reset: ok"

    @rx.event
    def disarm(self):
        self.load_mode = ""
        self.result = "disarm: ok"

    @rx.event
    def ping(self):
        self.result = (
            f"ping@{time.time():.3f}: a={self.a} b={self.b} c={self.c} count={self.count} status={self.status!r} "
            f"partial={list(self.partial_log)} done={list(self.done_log)} cv={self.b_times_ten} bg={self.bg_status!r}"
        )

    @rx.event
    def raise_after_yield(self):
        self.a = 1
        yield
        self.b = 2
        msg = "after yield"
        raise ValueError(msg)

    @rx.event
    def raise_no_yield(self):
        self.c = 3
        self.partial_log.append("rny")
        msg = "no yield"
        raise ValueError(msg)

    @rx.event
    async def raise_other(self):
        other = await self.get_state(Other)
        other.n += 1
        msg = "after writing Other"
        raise ValueError(msg)

    @rx.event(supersedes=True)
    async def sup(self, q: str):
        self.count += 1
        self.status = f"start {q}"
        yield
        await asyncio.sleep(1.0)
        self.partial_log.append(q)
        self.c += 10
        await asyncio.sleep(1.0)
        self.done_log.append(q)
        self.status = f"done {q}"

    @rx.event(background=True, supersedes=True)
    async def bg_linked(self, mode: str):
        async with self:
            linked = await self.get_state(Other)
            self.bg_status = f"armed {mode!r}"
            self.load_mode = mode
        try:
            async with linked:
                linked.n += 1
        except BaseException as ex:
            print(f"BG_LINKED mode={mode!r} ended with {type(ex).__name__}: {ex} t={time.time():.3f}", flush=True)
            raise
        async with self:
            self.bg_status = f"finished {mode!r}"

    @rx.event
    def ret_value(self):
        self.a = 5
        return self.a

    @rx.event
    def ret_garbage(self):
        self.a = 6
        return rx.redirect

    @rx.event
    def ret_self_handler(self):
        # the documented pitfall: returning the bound method instead of the class reference
        self.a = 8
        return self.chained

    @rx.event
    def ret_self_handler_call(self):
        self.a = 9
        return self.chained(4)

    @rx.event
    def chain(self):
        self.a = 7
        return F.chained(1)

    @rx.event
    def chained(self, v: int):
        self.b = v

    @rx.event
    def gated_plain(self):
        self.gated_runs += 1

    @rx.event
    async def gated_upload(self, files: list[rx.UploadFile]):
        self.gated_runs += 1
        self.result = f"gated_upload: ran {len(files)}"


class Gate(rx.Middleware):
    """Records every event; blocks handlers named gated_*."""

    async def preprocess(self, app, state, event):
        with open(MW_LOG, "a") as f:
            f.write(json.dumps({"name": event.name, "payload_keys": sorted(event.payload), "has_router_data": bool(event.router_data)}) + "\n")
        if event.name.rpartition(".")[2].startswith("gated_"):
            return StateUpdate(events=[Event(name="_call_function", payload={"function": "() => {window.__blocked = (window.__blocked || 0) + 1}", "callback": None})])
        return None


D_BUTTONS = [
    "plain", "undecorated", "below", "above", "above_async", "below_async", "above_gen",
    "bg_below", "uses_helpers", "mix_plain",
]


def _double_row(label: str):
    cls = DOUBLE.get(label)
    if cls is None:
        return rx.text(f"[{label}: class not created]", id=f"d-{label}-err")
    return rx.hstack(
        rx.button(label, on_click=cls.h, id=f"d-{label}", size="1"),
        rx.text(cls.out, id=f"out-{label}"),
    )


def _safe_button(name: str):
    try:
        if not hasattr(D, name):
            return rx.text(f"[{name}: not defined]", id=f"d-{name}-err")
        return rx.button(name, on_click=getattr(D, name), id=f"d-{name}", size="1")
    except Exception as ex:
        IMPORT_RESULTS[f"button:{name}"] = f"!{type(ex).__name__}: {str(ex)[:160]}"
        return rx.text(f"[{name}: {type(ex).__name__}]", id=f"d-{name}-err")


def _safe(label: str, make):
    try:
        return make()
    except Exception as ex:
        IMPORT_RESULTS[f"button:{label}"] = f"!{type(ex).__name__}: {str(ex)[:160]}"
        return rx.text(f"[{label}: {type(ex).__name__}]", id=f"d-{label}-err")


def deco() -> rx.Component:
    return rx.vstack(
        rx.heading("decorators"),
        rx.hstack(rx.text("out"), rx.text(D.out, id="out")),
        rx.hstack(rx.text("calls"), rx.text(D.calls.join(","), id="calls")),
        rx.hstack(rx.text("summary"), rx.text(D.summary, id="summary")),
        rx.button("reset", on_click=D.reset_d, id="d-reset"),
        rx.flex(*[_safe_button(n) for n in D_BUTTONS], wrap="wrap", spacing="1"),
        rx.flex(
            _safe("above_args", lambda: rx.button("above_args", on_click=D.above_args(5, "z"), id="d-above_args")),
            _safe("decentralized", lambda: rx.button("decentralized", on_click=decentralized(5), id="d-decentralized")),
            _safe("decentralized_str", lambda: rx.button("decentralized_str", on_click=decentralized_str(6), id="d-decentralized_str")),
            _safe("helper_fn", lambda: rx.button("helper_fn", on_click=helper_fn, id="d-helper_fn")),
            _safe("static_over", lambda: rx.button("static_over", on_click=D.static_over, id="d-static_over")),
            wrap="wrap", spacing="1",
        ),
        *[_double_row(n) for n in ("double_plain", "double_bg", "double_bg_rev", "double_throttle", "double_throttle_rev")],
        rx.el.pre(json.dumps(IMPORT_RESULTS, indent=1), id="import-results"),
        rx.link("fail page", href="/fail"),
        padding="1em",
    )


def _o(label, var, ident):
    return rx.hstack(rx.text(label, weight="bold"), rx.text(var, id=ident))


def fail() -> rx.Component:
    return rx.vstack(
        rx.heading("failure paths"),
        _o("result", F.result, "result"),
        _o("a", F.a, "a"), _o("b", F.b, "b"), _o("c", F.c, "c"),
        _o("cv", F.b_times_ten, "cv"),
        _o("status", F.status, "status"), _o("count", F.count, "count"),
        _o("partial", F.partial_log.join(","), "partial"), _o("done", F.done_log.join(","), "done"),
        _o("bg", F.bg_status, "bg"), _o("other.n", Other.n, "other-n"), _o("gated_runs", F.gated_runs, "gated-runs"),
        rx.flex(
            rx.button("reset", on_click=F.reset_f, id="f-reset"),
            rx.button("ping", on_click=F.ping, id="f-ping"),
            rx.button("disarm", on_click=F.disarm, id="f-disarm"),
            rx.button("raise_after_yield", on_click=F.raise_after_yield, id="f-raise_after_yield"),
            rx.button("raise_no_yield", on_click=F.raise_no_yield, id="f-raise_no_yield"),
            rx.button("raise_other", on_click=F.raise_other, id="f-raise_other"),
            rx.button("sup a", on_click=F.sup("a"), id="f-sup-a"),
            rx.button("sup b", on_click=F.sup("b"), id="f-sup-b"),
            rx.button("bg fail", on_click=F.bg_linked("fail"), id="f-bg-fail"),
            rx.button("bg slow", on_click=F.bg_linked("slow"), id="f-bg-slow"),
            rx.button("bg ok", on_click=F.bg_linked(""), id="f-bg-ok"),
            rx.button("ret_value", on_click=F.ret_value, id="f-ret_value"),
            rx.button("ret_garbage", on_click=F.ret_garbage, id="f-ret_garbage"),
            rx.button("chain", on_click=F.chain, id="f-chain"),
            rx.button("ret_self_handler", on_click=F.ret_self_handler, id="f-ret_self_handler"),
            rx.button("ret_self_handler_call", on_click=F.ret_self_handler_call, id="f-ret_self_handler_call"),
            rx.button("gated_plain", on_click=F.gated_plain, id="f-gated_plain"),
            wrap="wrap", spacing="1",
        ),
        rx.upload(rx.text("drop"), id="u1"),
        rx.button("gated upload", on_click=F.gated_upload(rx.upload_files(upload_id="u1")), id="f-gated_upload"),
        rx.link("deco page", href="/"),
        padding="1em",
    )


app = rx.App()
app.add_middleware(Gate())
app.add_page(deco, route="/")
app.add_page(fail, route="/fail")
