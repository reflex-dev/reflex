"""Await matrix for reflex 0.11.0a1 (#7673 / #7782): every case writes `Main.result = "<case>: ..."`."""

from __future__ import annotations

import asyncio
import dataclasses
import datetime

import reflex as rx

from .mw import AuthGate, Mutator, RecorderMiddleware


@dataclasses.dataclass
class Item:
    name: str
    qty: int = 1


class Auth(rx.State):
    logged_in: bool = False
    blocked_count: int = 0

    @rx.event
    def login(self):
        self.logged_in = True

    @rx.event
    def logout(self):
        self.logged_in = False
        self.blocked_count = 0


class Other(rx.State):
    """A state unrelated to Main (sibling under the root)."""

    items: list[str] = []
    n: int = 0

    @rx.event
    def record(self, item: str) -> int:
        self.items.append(item)
        self.n = len(self.items)
        return self.n

    @rx.event
    def where(self) -> str:
        return f"path={self.router.url.path}"

    @rx.event
    async def call_main(self, amount: int):
        got = await Main.add(amount)
        self.items.append(f"main={got}")
        self.n = len(self.items)
        main = await self.get_state(Main)
        main.result = f"other_to_main: {got}"

    @rx.event
    def clear(self):
        self.items = []
        self.n = 0


class LogMixin(rx.State, mixin=True):
    mlog: list[str] = []

    @rx.event
    def mlog_add(self, s: str) -> int:
        self.mlog.append(s)
        return len(self.mlog)


class Main(LogMixin, rx.State):
    total: int = 0
    last_added: int = 0
    result: str = ""
    progress: int = 0
    depth: int = 0
    query: str = ""
    data: dict[str, int] = {"a": 1}
    rows: list[dict[str, int]] = [{"x": 1}]
    uploaded: list[str] = []
    secret_runs: int = 0

    @rx.var
    def doubled(self) -> int:
        return self.total * 2

    @rx.event
    async def reset_all(self):
        self.reset()
        other = await self.get_state(Other)
        other.clear()
        sub = await self.get_state(Sub)
        sub.reset()
        self.result = "reset: ok"

    @rx.event
    def ping(self):
        self.result = f"ping: ok total={self.total}"

    # -- the docs example ---------------------------------------------------
    @rx.event
    def add(self, amount: int) -> int:
        """Add to the total and return the new total."""
        self.total += amount
        self.last_added = amount
        return self.total

    @rx.event
    async def add_twice(self, amount: int):
        first = await type(self).add(amount)
        second = await type(self).add(amount)
        self.result = f"add_twice: {first} then {second}"
        yield rx.toast(f"{first} then {second}")

    # -- targets ------------------------------------------------------------
    @rx.event
    def no_args(self) -> str:
        self.progress += 1
        return "no_args_value"

    @rx.event
    def gen_sync(self, n: int):
        for i in range(n):
            self.progress = i + 1
            yield
        return "gen_sync_return"  # noqa: B901

    @rx.event
    async def gen_async(self, n: int):
        for i in range(n):
            await asyncio.sleep(0.3)
            self.progress = i + 1
            yield

    @rx.event
    def ret_toast(self):
        self.progress = 11
        return rx.toast("from ret_toast")

    @rx.event
    def ret_events(self):
        self.progress = 12
        return [rx.toast("from ret_events"), Main.add(100)]

    @rx.event
    def ret_empty_list(self):
        return []

    @rx.event
    def ret_dict(self) -> dict:
        return {"when": datetime.datetime(2026, 11, 11, 12, 0), "item": Item("a", 2)}

    @rx.event
    def boom(self, amount: int = 1000):
        self.total += amount
        msg = "boom"
        raise ValueError(msg)

    @rx.event
    async def slow(self, secs: float) -> str:
        self.progress = 1
        await asyncio.sleep(secs)
        self.progress = 2
        return "slow_done"

    @rx.event
    async def fact(self, n: int) -> int:
        self.depth = max(self.depth, n)
        if n <= 1:
            return 1
        return n * await type(self).fact(n - 1)

    @rx.event
    async def recurse_forever(self):
        self.depth += 1
        await type(self).recurse_forever()

    @rx.event(throttle=1000)
    def throttled(self) -> str:
        self.progress += 1
        return "throttled_value"

    @rx.event(debounce=500)
    def debounced(self) -> str:
        self.progress += 1
        return "debounced_value"

    @rx.event(supersedes=True)
    async def search(self, q: str) -> str:
        await asyncio.sleep(0.6)
        self.query = q
        return q.upper()

    @rx.event
    def takes_dict(self, d: dict[str, int]) -> int:
        d["mutated_by_callee"] = 1
        return len(d)

    @rx.event
    def takes_list(self, rows: list[dict[str, int]]) -> int:
        rows.append({"mutated_by_callee": 1})
        return len(rows)

    @rx.event
    def takes_item(self, item: Item) -> str:
        return f"{type(item).__name__}:{item}"

    @rx.event
    def takes_dt(self, when: datetime.datetime) -> str:
        return f"{type(when).__name__}:{when.isoformat()}"

    @rx.event
    def mutate_me(self, amount: int) -> int:
        self.total += amount
        return amount

    @rx.event
    def mw_raise(self) -> str:
        return "mw_raise_ran"

    @rx.event
    def secret_add(self, amount: int) -> int:
        self.secret_runs += 1
        self.total += amount
        return self.total

    @rx.event(background=True)
    async def bg_worker(self, n: int) -> str:
        await asyncio.sleep(0.2)
        async with self:
            self.total += n
        return f"worker{n}"

    # -- cases: foreground --------------------------------------------------
    @rx.event
    async def c_sub(self):
        r = await Sub.bump(2)
        r2 = await Sub.bump(3)
        self.result = f"c_sub: {r},{r2}"

    @rx.event
    async def c_other(self):
        r = await Other.record("x")
        w = await Other.where()
        self.result = f"c_other: {r} {w}"

    @rx.event
    async def c_other_get_state(self):
        other = await self.get_state(Other)
        plain = other.record("plain")
        try:
            r = await other.record("awaited")
        except Exception as ex:
            r = f"{type(ex).__name__}: {ex}"
        self.result = f"c_other_get_state: plain={plain} awaited={r}"

    @rx.event
    async def c_mixin(self):
        r = await Main.mlog_add("m1")
        r2 = await type(self).mlog_add("m2")
        self.result = f"c_mixin: {r},{r2} mlog={list(self.mlog)}"

    @rx.event
    async def c_no_args(self):
        r = await Main.no_args
        r2 = await Main.no_args()
        self.result = f"c_no_args: {r},{r2}"

    @rx.event
    async def c_gen_sync(self):
        r = await Main.gen_sync(3)
        self.result = f"c_gen_sync: {r!r}"

    @rx.event
    async def c_gen_async(self):
        r = await Main.gen_async(3)
        self.result = f"c_gen_async: {r!r}"

    @rx.event
    async def c_ret_toast(self):
        r = await Main.ret_toast()
        self.result = f"c_ret_toast: {r!r}"

    @rx.event
    async def c_ret_events(self):
        r = await Main.ret_events()
        self.result = f"c_ret_events: {r!r} total_now={self.total}"

    @rx.event
    async def c_ret_empty_list(self):
        r = await Main.ret_empty_list()
        self.result = f"c_ret_empty_list: {r!r}"

    @rx.event
    async def c_ret_dict(self):
        r = await Main.ret_dict()
        self.result = f"c_ret_dict: {type(r['when']).__name__} {type(r['item']).__name__}"

    @rx.event
    async def c_await_frontend(self):
        try:
            r = await rx.toast("awaited toast")
        except Exception as ex:
            r = f"{type(ex).__name__}: {ex}"
        try:
            r2 = await rx.redirect("/onload")
        except Exception as ex:
            r2 = f"{type(ex).__name__}: {ex}"
        self.result = f"c_await_frontend: {r} || {r2}"

    @rx.event
    async def c_boom_caught(self):
        try:
            await Main.boom(1000)
        except ValueError as ex:
            self.result = f"c_boom_caught: {ex} total={self.total}"

    @rx.event
    async def c_boom_uncaught(self):
        self.last_added = -1
        await Main.boom(1000)
        self.result = "c_boom_uncaught: unreachable"

    @rx.event
    async def c_fact(self):
        r = await Main.fact(10)
        self.result = f"c_fact: {r} depth={self.depth}"

    @rx.event
    async def c_recurse(self):
        try:
            await Main.recurse_forever()
        except RecursionError as ex:
            self.result = f"c_recurse: RecursionError depth={self.depth} {str(ex)[:40]}"

    @rx.event
    async def c_actions(self):
        a = await Main.throttled()
        b = await Main.throttled()
        c = await Main.debounced()
        d = await Main.add(1).throttle(500)
        e = await Main.add(1).stop_propagation
        self.result = f"c_actions: {a},{b},{c},{d},{e} progress={self.progress}"

    @rx.event
    async def c_supersedes(self, q: str):
        r = await Main.search(q)
        self.result = f"c_supersedes: {r} query={self.query}"

    @rx.event
    async def c_self_sync(self):
        try:
            r = await self.add(5)
        except Exception as ex:
            r = f"{type(ex).__name__}: {ex}"
        self.result = f"c_self_sync: {r} total={self.total}"

    @rx.event
    async def c_self_async(self):
        r = await self.slow(0.05)
        r2 = await self.fact(3)
        self.result = f"c_self_async: {r},{r2}"

    @rx.event
    async def c_self_gen(self):
        try:
            r = await self.gen_async(2)
        except Exception as ex:
            r = f"{type(ex).__name__}: {ex}"
        self.result = f"c_self_gen: {r} progress={self.progress}"

    @rx.event
    async def c_args(self):
        out = []
        for label, call in (
            ("str->int", lambda: Main.add("5")),
            ("kw", lambda: Main.add(amount=2)),
            ("item", lambda: Main.takes_item(Item("a", 2))),
            ("item_dict", lambda: Main.takes_item({"name": "b", "qty": 3})),
            ("dt", lambda: Main.takes_dt(datetime.datetime(2026, 11, 11, 12, 0))),
            ("dt_str", lambda: Main.takes_dt("2026-11-11T12:00:00")),
            ("bad_int", lambda: Main.add("abc")),
            ("too_many", lambda: Main.add(1, 2)),
            ("missing", lambda: Main.add()),
        ):
            try:
                out.append(f"{label}={await call()!r}")
            except Exception as ex:
                out.append(f"{label}!{type(ex).__name__}:{str(ex)[:70]}")
        self.result = "c_args: " + " | ".join(out)

    @rx.event
    async def c_proxied(self):
        # #7673 bugfix: proxied dict then proxied list
        a = await Main.takes_dict(self.data)
        b = await Main.takes_list(self.rows)
        c = await Main.takes_dict(self.data)
        self.result = f"c_proxied: {a},{b},{c} data={dict(self.data)} rows={len(self.rows)}"

    @rx.event
    def c_proxied_yield(self):
        # same bug through the pre-existing chaining API (works on 0.10.1?)
        yield Main.takes_dict(self.data)
        yield Main.takes_list(self.rows)
        self.result = "c_proxied_yield: ok"

    @rx.event
    async def c_gather(self):
        r = await asyncio.gather(Main.add(1), Main.add(10), Main.slow(0.2), Other.record("g"))
        self.result = f"c_gather: {r} total={self.total}"

    @rx.event
    async def c_ensure_future(self):
        fut = asyncio.ensure_future(Main.slow(0.5))
        await asyncio.sleep(0)
        self.result = f"c_ensure_future: returned-before-task done={fut.done()}"

    @rx.event
    async def c_create_task(self):
        try:
            t = asyncio.create_task(Main.add(1))
            r = await t
        except Exception as ex:
            r = f"{type(ex).__name__}: {ex}"
        self.result = f"c_create_task: {r}"

    @rx.event
    async def c_wait_for(self):
        try:
            r = await asyncio.wait_for(Main.slow(5), timeout=0.2)
        except Exception as ex:
            r = f"{type(ex).__name__}"
        self.result = f"c_wait_for: {r} progress={self.progress}"

    @rx.event
    async def c_setvar(self):
        r = await Main.setvar("progress", 42)
        self.result = f"c_setvar: {r!r} progress={self.progress}"

    @rx.event
    async def c_fg_await_bg(self):
        try:
            r = await Main.bg_worker(1)
        except Exception as ex:
            r = f"{type(ex).__name__}: {ex}"
        self.result = f"c_fg_await_bg: {r}"

    @rx.event
    def c_sync_await(self):
        # a sync handler cannot await; what does the natural mistake give?
        r = Main.add(5)
        self.result = f"c_sync_await: {type(r).__name__} total={self.total}"

    @rx.event
    async def c_upload_spec(self):
        try:
            r = await Main.handle_upload(rx.upload_files("u1"))
        except Exception as ex:
            r = f"{type(ex).__name__}: {ex}"
        self.result = f"c_upload_spec: {r}"

    # -- cases: middleware --------------------------------------------------
    @rx.event
    async def c_mw_blocked(self):
        before = self.total
        r = await Main.secret_add(5)
        self.result = f"c_mw_blocked: {r!r} total {before}->{self.total} runs={self.secret_runs}"

    @rx.event
    async def c_mw_mutate(self):
        r = await Main.mutate_me(3)
        self.result = f"c_mw_mutate: {r!r} total={self.total}"

    @rx.event
    async def c_mw_raise(self):
        try:
            r = await Main.mw_raise()
        except Exception as ex:
            r = f"{type(ex).__name__}: {ex}"
        self.result = f"c_mw_raise: {r}"

    @rx.event
    async def c_mw_self_bypass(self):
        # `self.secret_add()` is the plain method: no middleware
        r = self.secret_add(5)
        self.result = f"c_mw_self_bypass: {r!r} runs={self.secret_runs}"

    @rx.event(background=True)
    async def c_mw_bg_blocked(self):
        r_out = await Main.secret_add(5)
        async with self:
            r_in = await Main.secret_add(5)
            self.result = f"c_mw_bg_blocked: out={r_out!r} in={r_in!r} runs={self.secret_runs}"

    # -- cases: background --------------------------------------------------
    @rx.event(background=True)
    async def c_bg_outside(self):
        r = await Main.add(7)
        g = await Main.gen_async(2)
        async with self:
            self.result = f"c_bg_outside: {r} gen={g!r} total={self.total}"

    @rx.event(background=True)
    async def c_bg_inside(self):
        async with self:
            r = await Main.add(7)
            o = await Other.record("bg")
            s = await Sub.bump(1)
            self.result = f"c_bg_inside: {r},{o},{s}"

    @rx.event(background=True)
    async def c_bg_await_bg(self):
        r = await Main.bg_worker(2)
        async with self:
            self.result = f"c_bg_await_bg: {r!r} total={self.total}"

    @rx.event(background=True)
    async def c_bg_inside_await_bg(self):
        async with self:
            try:
                r = await Main.bg_worker(3)
            except Exception as ex:
                r = f"{type(ex).__name__}: {ex}"
            self.result = f"c_bg_inside_await_bg: {r}"

    @rx.event(background=True)
    async def c_bg_boom(self):
        try:
            await Main.boom(1000)
            r = "no-exception"
        except Exception as ex:
            r = f"{type(ex).__name__}: {ex}"
        async with self:
            self.result = f"c_bg_boom: {r} total={self.total}"

    @rx.event(background=True)
    async def c_bg_gather(self):
        r = await asyncio.gather(Main.add(1), Main.add(10), Other.record("bgg"))
        async with self:
            self.result = f"c_bg_gather: {r} total={self.total}"

    @rx.event(background=True)
    async def c_bg_supersedes(self, q: str):
        try:
            r = await Main.search(q)
        except BaseException as ex:
            r = f"{type(ex).__name__}"
            async with self:
                self.result = f"c_bg_supersedes: {q} -> {r}"
            raise
        async with self:
            self.result = f"c_bg_supersedes: {q} -> {r} query={self.query}"

    @rx.event(background=True)
    async def c_bg_self(self):
        # natural mistakes inside a background task
        out = []
        try:
            out.append(f"self.add={await self.add(1)}")
        except Exception as ex:
            out.append(f"self.add!{type(ex).__name__}: {str(ex)[:80]}")
        async with self:
            try:
                out.append(f"locked self.slow={await self.slow(0.05)}")
            except Exception as ex:
                out.append(f"locked self.slow!{type(ex).__name__}: {str(ex)[:80]}")
            self.result = "c_bg_self: " + " | ".join(out)

    # -- upload / on_load ---------------------------------------------------
    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        sizes = []
        for f in files:
            data = await f.read()
            sizes.append(await Main.add(len(data)))
            self.uploaded.append(f.name or "?")
        o = await Other.record(f"upload:{len(files)}")
        self.result = f"upload: sizes={sizes} other={o}"

    @rx.event
    async def secret_upload(self, files: list[rx.UploadFile]):
        self.secret_runs += 1
        self.result = f"secret_upload: ran with {len(files)} file(s)"

    @rx.event
    async def load_page(self):
        r = await Main.add(1)
        o = await Other.record("loaded")
        w = await Other.where()
        self.result = f"on_load: {r} {o} {w}"


class Sub(Main):
    """Substate of Main."""

    n: int = 0
    note: str = ""

    @rx.event
    def bump(self, by: int) -> int:
        self.n += by
        return self.n

    @rx.event
    async def c_parent(self):
        a = await Main.add(3)
        b = await type(self).add(3)
        c = await Sub.add(3)
        self.note = f"{a},{b},{c}"
        self.result = f"c_parent: {a},{b},{c} total={self.total}"


class Counter(rx.ComponentState):
    count: int = 0
    msg: str = ""

    @rx.event
    def incr(self, n: int) -> int:
        self.count += n
        return self.count

    @rx.event
    async def incr2(self):
        a = await type(self).incr(1)
        b = await Main.add(1)
        self.msg = f"cs: {a}/{b}"

    @classmethod
    def get_component(cls, **props):
        ident = props.pop("ident")
        return rx.hstack(
            rx.button("cs incr2", on_click=cls.incr2, id=f"b-cs-{ident}"),
            rx.text(cls.msg, id=f"cs-msg-{ident}"),
            rx.text(cls.count, id=f"cs-count-{ident}"),
        )


FG_CASES = [
    "add_twice:5",
    "c_sub",
    "c_other",
    "c_other_get_state",
    "c_mixin",
    "c_no_args",
    "c_gen_sync",
    "c_gen_async",
    "c_ret_toast",
    "c_ret_events",
    "c_ret_empty_list",
    "c_ret_dict",
    "c_await_frontend",
    "c_boom_caught",
    "c_boom_uncaught",
    "c_fact",
    "c_recurse",
    "c_actions",
    "c_self_sync",
    "c_self_async",
    "c_self_gen",
    "c_args",
    "c_proxied",
    "c_proxied_yield",
    "c_gather",
    "c_ensure_future",
    "c_create_task",
    "c_wait_for",
    "c_setvar",
    "c_fg_await_bg",
    "c_sync_await",
    "c_upload_spec",
    "c_mw_blocked",
    "c_mw_mutate",
    "c_mw_raise",
    "c_mw_self_bypass",
    "c_mw_bg_blocked",
    "c_bg_outside",
    "c_bg_inside",
    "c_bg_await_bg",
    "c_bg_inside_await_bg",
    "c_bg_boom",
    "c_bg_gather",
    "c_bg_self",
]


def _case_button(case: str) -> rx.Component:
    name, _, arg = case.partition(":")
    handler = getattr(Main, name)
    return rx.button(name, on_click=handler(int(arg)) if arg else handler, id=f"b-{name}", size="1")


def out(label: str, var, ident: str) -> rx.Component:
    return rx.hstack(rx.text(label, weight="bold"), rx.text(var, id=ident))


def index() -> rx.Component:
    return rx.vstack(
        rx.heading("await matrix"),
        out("result", Main.result, "result"),
        out("total", Main.total, "total"),
        out("doubled", Main.doubled, "doubled"),
        out("last_added", Main.last_added, "last_added"),
        out("progress", Main.progress, "progress"),
        out("depth", Main.depth, "depth"),
        out("query", Main.query, "query"),
        out("secret_runs", Main.secret_runs, "secret_runs"),
        out("sub.n", Sub.n, "sub-n"),
        out("other.items", Other.items.join(","), "other-items"),
        out("uploaded", Main.uploaded.join(","), "uploaded"),
        out("auth", rx.cond(Auth.logged_in, "in", "out"), "auth"),
        out("blocked_count", Auth.blocked_count, "blocked-count"),
        rx.hstack(
            rx.button("reset", on_click=Main.reset_all, id="b-reset"),
            rx.button("ping", on_click=Main.ping, id="b-ping"),
            rx.button("login", on_click=Auth.login, id="b-login"),
            rx.button("logout", on_click=Auth.logout, id="b-logout"),
            rx.button("add direct (returns int)", on_click=Main.add(5), id="b-add-direct"),
            rx.button("ret_dict direct", on_click=Main.ret_dict, id="b-ret-dict-direct"),
            rx.button("secret_add direct", on_click=Main.secret_add(5), id="b-secret-direct"),
            rx.button("mutate_me direct", on_click=Main.mutate_me(3), id="b-mutate-direct"),
            rx.button("Sub.c_parent", on_click=Sub.c_parent, id="b-c_parent"),
            rx.button("Other.call_main", on_click=Other.call_main(4), id="b-other_to_main"),
            wrap="wrap",
        ),
        rx.flex(*[_case_button(c) for c in FG_CASES], wrap="wrap", spacing="1"),
        rx.hstack(
            rx.input(id="q", default_value="abc"),
            rx.button("c_supersedes a", on_click=Main.c_supersedes("first"), id="b-sup-1"),
            rx.button("c_supersedes b", on_click=Main.c_supersedes("second"), id="b-sup-2"),
            rx.button("search a (direct)", on_click=Main.search("dfirst"), id="b-search-1"),
            rx.button("search b (direct)", on_click=Main.search("dsecond"), id="b-search-2"),
            rx.button("c_bg_supersedes a", on_click=Main.c_bg_supersedes("bgfirst"), id="b-bgsup-1"),
            rx.button("c_bg_supersedes b", on_click=Main.c_bg_supersedes("bgsecond"), id="b-bgsup-2"),
            wrap="wrap",
        ),
        Counter.create(ident="a"),
        Counter.create(ident="b"),
        rx.upload(rx.text("drop"), id="u1", multiple=True),
        rx.hstack(
            rx.button(
                "upload",
                on_click=Main.handle_upload(rx.upload_files(upload_id="u1")),
                id="b-upload",
            ),
            rx.button(
                "secret upload",
                on_click=Main.secret_upload(rx.upload_files(upload_id="u1")),
                id="b-secret-upload",
            ),
        ),
        rx.link("onload page", href="/onload", id="l-onload"),
        spacing="2",
        padding="1em",
    )


def onload() -> rx.Component:
    return rx.vstack(
        rx.heading("onload"),
        out("result", Main.result, "result"),
        out("total", Main.total, "total"),
        out("other.items", Other.items.join(","), "other-items"),
        rx.link("home", href="/", id="l-home"),
    )


app = rx.App()
app.add_middleware(RecorderMiddleware())
app.add_middleware(AuthGate())
app.add_middleware(Mutator())
app.add_page(index, route="/")
app.add_page(onload, route="/onload", on_load=Main.load_page)
