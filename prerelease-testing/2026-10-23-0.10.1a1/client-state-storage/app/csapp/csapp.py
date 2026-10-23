"""Prerelease test app for cluster client-state-storage (reflex 0.10.1a1)."""

import asyncio
import os

import reflex as rx

# Guard: this app must run from a PyPI venv, never the checkout.
assert "/scratchpad/prt/envs/" in rx.__file__, rx.__file__

# Server-side evaluation counters, exposed through an event handler.
EVALS: dict[str, int] = {"derived": 0, "derived_cookie": 0}

shared = rx._x.client_state(default="initial", var_name="sharedcs")
pushed = rx._x.client_state(default="not-pushed", var_name="pushedcs")
pushed_bg = rx._x.client_state(default="bg-not-pushed", var_name="pushedbgcs")


class State(rx.State):
    show: bool = False
    show_bg: bool = False
    items: list[str] = ["a", "b", "c"]
    load_count: int = 0
    bg_status: str = "idle"

    @rx.event
    def reveal(self):
        self.show = True

    @rx.event
    def reveal_bg(self):
        self.show_bg = True

    @rx.event
    def push_from_on_load(self):
        # Pushes before any pushed-reader has mounted (reader is behind rx.cond).
        self.load_count += 1
        return pushed.push(f"pushed-on-load-{self.load_count}")

    @rx.event
    def push_value(self):
        return pushed.push("pushed-by-click")

    @rx.event
    def push_default(self):
        return pushed.push("not-pushed")

    @rx.event
    def push_none(self):
        return pushed.push(None)

    @rx.event(background=True)
    async def bg_push(self):
        async with self:
            self.bg_status = "running"
        await asyncio.sleep(1.0)
        async with self:
            self.bg_status = "pushed"
        yield pushed_bg.push("pushed-from-bg")


@rx.memo
def memo_reader() -> rx.Component:
    return rx.text(shared.value, id="memo-reader")


def index() -> rx.Component:
    return rx.vstack(
        rx.heading("client_state page"),
        rx.hstack(
            rx.button("set", on_click=shared.set_value("clicked"), id="setter"),
            rx.button("reset", on_click=shared.set_value("initial"), id="resetter"),
            rx.button("reveal", on_click=State.reveal, id="reveal"),
            rx.button("reveal-bg", on_click=State.reveal_bg, id="reveal-bg"),
        ),
        rx.hstack(
            rx.button("push", on_click=State.push_value, id="pusher"),
            rx.button("push-default", on_click=State.push_default, id="push-default"),
            rx.button("push-none", on_click=State.push_none, id="push-none"),
            rx.button("bg-push", on_click=State.bg_push, id="bg-pusher"),
        ),
        rx.text("always:", rx.text(shared.value, id="always-reader", as_="span")),
        memo_reader(),
        rx.cond(State.show, rx.text(shared.value, id="late-reader")),
        rx.cond(State.show, rx.text(pushed.value, id="pushed-reader")),
        rx.cond(State.show_bg, rx.text(pushed_bg.value, id="pushed-bg-reader")),
        rx.foreach(State.items, lambda it: rx.text(it, "=", shared.value, class_name="foreach-reader")),
        rx.text(State.bg_status, id="bg-status"),
        rx.text(State.load_count, id="load-count"),
        rx.link("second", href="/second", id="to-second"),
        rx.link("storage", href="/storage", id="to-storage"),
        rx.text(State.router.session.client_token, id="token"),
    )


def second() -> rx.Component:
    return rx.vstack(
        rx.heading("second page"),
        rx.text(shared.value, id="second-reader"),
        rx.text(pushed.value, id="second-pushed-reader"),
        rx.button("set2", on_click=shared.set_value("clicked-second"), id="setter2"),
        rx.button("push2", on_click=State.push_value, id="pusher2"),
        rx.link("index", href="/", id="to-index"),
        rx.text(State.load_count, id="load-count"),
    )


class SubA(rx.State):
    shared_a: str = rx.LocalStorage("", name="shared", sync=True)
    cookie_val: str = rx.Cookie("", name="mycookie")
    sess_val: str = rx.SessionStorage("", name="mysess")
    count_display: str = ""
    plain_counter: int = 0

    @rx.event
    def set_shared_a(self, v: str):
        self.shared_a = v

    @rx.event
    def set_cookie_val(self, v: str):
        self.cookie_val = v

    @rx.event
    def set_sess_val(self, v: str):
        self.sess_val = v

    @rx.event
    def bump(self):
        self.plain_counter += 1

    @rx.event
    def read_counts(self):
        self.count_display = f"derived={EVALS['derived']} derived_cookie={EVALS['derived_cookie']}"

    @rx.event
    def reset_counts(self):
        EVALS["derived"] = 0
        EVALS["derived_cookie"] = 0
        self.count_display = "reset"

    @rx.var(cache=True)
    def derived(self) -> str:
        EVALS["derived"] += 1
        print(f"[EVAL] derived #{EVALS['derived']} shared_a={self.shared_a!r}", flush=True)
        return f"derived({self.shared_a})"

    @rx.var(cache=True)
    def derived_cookie(self) -> str:
        EVALS["derived_cookie"] += 1
        print(f"[EVAL] derived_cookie #{EVALS['derived_cookie']}", flush=True)
        return f"dc({self.cookie_val}|{self.sess_val})"


class SubB(rx.State):
    shared_b: str = rx.LocalStorage("", name="shared", sync=True)
    other: str = rx.LocalStorage("", name="other", sync=True)

    @rx.event
    def set_shared_b(self, v: str):
        self.shared_b = v

    @rx.event
    def set_other(self, v: str):
        self.other = v


class Nested(SubB):
    shared_n: str = rx.LocalStorage("", name="shared", sync=True)


def storage() -> rx.Component:
    return rx.vstack(
        rx.heading("storage page"),
        rx.input(value=SubA.shared_a, on_change=SubA.set_shared_a, id="in-a"),
        rx.input(value=SubB.shared_b, on_change=SubB.set_shared_b, id="in-b"),
        rx.input(value=SubB.other, on_change=SubB.set_other, id="in-other"),
        rx.input(value=SubA.cookie_val, on_change=SubA.set_cookie_val, id="in-cookie"),
        rx.input(value=SubA.sess_val, on_change=SubA.set_sess_val, id="in-sess"),
        rx.text("a=", SubA.shared_a, id="out-a"),
        rx.text("b=", SubB.shared_b, id="out-b"),
        rx.text("n=", Nested.shared_n, id="out-n"),
        rx.text("other=", SubB.other, id="out-other"),
        rx.text("cookie=", SubA.cookie_val, id="out-cookie"),
        rx.text("sess=", SubA.sess_val, id="out-sess"),
        rx.text(SubA.derived, id="derived"),
        rx.text(SubA.derived_cookie, id="derived-cookie"),
        rx.text(SubA.count_display, id="counts"),
        rx.text(SubA.plain_counter, id="plain-counter"),
        rx.hstack(
            rx.button("read-counts", on_click=SubA.read_counts, id="read-counts"),
            rx.button("reset-counts", on_click=SubA.reset_counts, id="reset-counts"),
            rx.button("bump", on_click=SubA.bump, id="bump"),
        ),
        rx.link("index", href="/", id="to-index"),
        rx.link("bloat", href="/bloat", id="to-bloat"),
        rx.text(rx.cond(State.is_hydrated, "true", "false"), id="hydrated"),
    )


class Bloat(rx.State):
    blob: str = rx.LocalStorage("", name="bloat")

    @rx.event
    def fill(self, n: int):
        self.blob = "x" * n

    @rx.event
    def clear(self):
        self.blob = ""

    @rx.var
    def blob_len(self) -> int:
        return len(self.blob)


def bloat() -> rx.Component:
    return rx.vstack(
        rx.heading("bloat page"),
        rx.text("len=", Bloat.blob_len, id="blob-len"),
        rx.button("fill-1.1MB", on_click=Bloat.fill(1_100_000), id="fill-big"),
        rx.button("fill-500k", on_click=Bloat.fill(500_000), id="fill-mid"),
        rx.button("clear", on_click=Bloat.clear, id="clear"),
        rx.text(rx.cond(State.is_hydrated, "true", "false"), id="hydrated"),
        rx.link("storage", href="/storage", id="to-storage"),
    )


class Expire(rx.State):
    count: int = 0
    bg_result: str = ""
    note: str = rx.LocalStorage("", name="expire-note")
    loads: int = 0

    @rx.event
    def on_load(self):
        self.loads += 1
        print(f"[EXPIRE] on_load #{self.loads}", flush=True)

    @rx.event
    def inc(self):
        self.count += 1

    @rx.event
    def set_note(self, v: str):
        self.note = v

    @rx.event(background=True)
    async def slow(self, seconds: int):
        async with self:
            self.bg_result = f"sleeping {seconds}s"
        await asyncio.sleep(seconds)
        async with self:
            self.bg_result = f"done after {seconds}s (count={self.count})"
            print(f"[EXPIRE] bg done; count={self.count} router={self.router.page.path!r}", flush=True)


def expire() -> rx.Component:
    return rx.vstack(
        rx.heading("expire page"),
        rx.text("count=", Expire.count, id="count"),
        rx.text("bg=", Expire.bg_result, id="bg-result"),
        rx.text("loads=", Expire.loads, id="loads"),
        rx.input(value=Expire.note, on_change=Expire.set_note, id="in-note"),
        rx.text("note=", Expire.note, id="out-note"),
        rx.hstack(
            rx.button("inc", on_click=Expire.inc, id="inc"),
            rx.button("slow-8", on_click=Expire.slow(8), id="slow"),
        ),
        rx.text(rx.cond(State.is_hydrated, "true", "false"), id="hydrated"),
        rx.text(State.router.session.client_token, id="token"),
        rx.link("index", href="/", id="to-index"),
    )


app = rx.App()
app.add_page(index, on_load=State.push_from_on_load)
app.add_page(second)
app.add_page(storage)
app.add_page(bloat)
app.add_page(expire, on_load=Expire.on_load)
