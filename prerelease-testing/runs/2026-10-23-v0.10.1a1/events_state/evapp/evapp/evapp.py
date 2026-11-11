"""Events app: EVT-06 (filtered uncached var), #7415 (on_load cancelled on disconnect), #7585 (background task
re-entering an expired Redis session), #7500 (dict views mutation reaches the UI).

Server-side steps are appended to ev_log.jsonl next to rxconfig.py so a driver can read what ran after the tab left.
"""

import asyncio
import json
import os
import pathlib
import time

import reflex as rx

assert f"/envs/{os.environ.get('EXPECT_VENV', 'new')}/" in rx.__file__, rx.__file__

LOG = pathlib.Path(__file__).resolve().parent.parent / "ev_log.jsonl"


def log(**rec):
    rec["t"] = round(time.time(), 3)
    with LOG.open("a") as f:
        f.write(json.dumps(rec, default=str) + "\n")


class FState(rx.State):
    """EVT-06: a cache=False var withheld by a get_delta override must be re-sent once released."""

    n: int = 0
    withhold: bool = False

    @rx.var(cache=False)
    def tick(self) -> int:
        return self.n * 100

    @rx.var(cache=False)
    async def atick(self) -> int:
        await asyncio.sleep(0)
        return self.n * 1000

    @rx.state._override_base_method
    def get_delta(self):
        delta = super().get_delta()
        if self.withhold:
            sub = delta.get(self.get_full_name(), {})
            sub.pop("tick_rx_state_", None)
            sub.pop("atick_rx_state_", None)
        return delta

    @rx.event
    def bump(self):
        self.n += 1

    @rx.event
    def set_withhold(self, v: bool):
        self.withhold = v


def filtered() -> rx.Component:
    return rx.vstack(
        rx.text("n=", rx.el.span(FState.n, id="n"), " tick=", rx.el.span(FState.tick, id="tick"), " atick=", rx.el.span(FState.atick, id="atick"), " withhold=", rx.el.span(FState.withhold.to_string(), id="withhold")),
        rx.button("bump", id="bump", on_click=FState.bump),
        rx.button("withhold on", id="won", on_click=FState.set_withhold(True)),
        rx.button("withhold off", id="woff", on_click=FState.set_withhold(False)),
    )


class LoadState(rx.State):
    """#7415: a multi-step on_load chain and an independent background task started from on_load."""

    steps: list[str] = []
    bg_steps: list[str] = []
    loads: int = 0

    @rx.event
    async def slow_load(self):
        self.loads += 1
        for i in range(1, 5):
            log(who="slow_load", step=i, loads=self.loads)
            self.steps.append(f"s{i}")
            yield
            await asyncio.sleep(1.2)
        log(who="slow_load", step="done", loads=self.loads)
        self.steps.append("done")

    @rx.event
    async def plain_slow_load(self):
        """A single await with no yield: is it cancelled mid-await?"""
        log(who="plain_slow_load", step="start")
        await asyncio.sleep(2.5)
        log(who="plain_slow_load", step="end")
        self.steps.append("plain-end")

    @rx.event(background=True)
    async def bg_from_load(self):
        for i in range(1, 5):
            await asyncio.sleep(1.0)
            log(who="bg_from_load", step=i)
            async with self:
                self.bg_steps.append(f"b{i}")
        log(who="bg_from_load", step="done")

    @rx.event
    def start_bg(self):
        log(who="start_bg", step="dispatch")
        return LoadState.bg_from_load


def onload() -> rx.Component:
    return rx.vstack(
        rx.text("steps=", rx.el.span(LoadState.steps.join(","), id="steps")),
        rx.text("bg=", rx.el.span(LoadState.bg_steps.join(","), id="bg")),
        rx.text("loads=", rx.el.span(LoadState.loads, id="loads")),
        rx.link("home", href="/", id="home"),
    )


class ExpState(rx.State):
    """#7585: a background task that sleeps past the Redis token expiration, then writes."""

    status: str = "idle"
    count: int = 0
    loads: int = 0
    pref: str = rx.LocalStorage("unset", name="ev_pref")

    @rx.event
    def on_load_count(self):
        self.loads += 1
        log(who="exp.on_load", loads=self.loads)

    @rx.event
    def set_pref(self, v: str):
        self.pref = v

    @rx.event
    def set_status(self, v: str):
        self.status = v

    @rx.event(background=True)
    async def long_task(self, sleep_s: int):
        async with self:
            self.status = "started"
            self.count += 1
            log(who="long_task", step="started", count=self.count)
        await asyncio.sleep(sleep_s)
        try:
            async with self:
                self.status = "done"
                self.count += 10
                log(who="long_task", step="done", count=self.count, loads=self.loads, pref=self.pref)
        except Exception as e:  # noqa: BLE001
            log(who="long_task", step="error", error=f"{type(e).__name__}: {e}")
            raise


def expire() -> rx.Component:
    return rx.vstack(
        rx.text("status=", rx.el.span(ExpState.status, id="status"), " count=", rx.el.span(ExpState.count, id="count"), " loads=", rx.el.span(ExpState.loads, id="loads"), " pref=", rx.el.span(ExpState.pref, id="pref")),
        rx.button("start 8s task", id="start8", on_click=ExpState.long_task(8)),
        rx.button("start 2s task", id="start2", on_click=ExpState.long_task(2)),
        rx.button("set pref", id="setpref", on_click=ExpState.set_pref("chosen")),
        rx.button("status=manual", id="manual", on_click=ExpState.set_status("manual")),
    )


class DState(rx.State):
    """#7500: mutate nested values reached through dict views; the UI and a cached var must update."""

    d: dict[str, list[str]] = {"a": ["a0"], "b": ["b0"]}

    @rx.var(cache=True)
    def summary(self) -> str:
        return ";".join(f"{k}={len(v)}" for k, v in self.d.items())

    @rx.event
    def via_values(self):
        for v in self.d.values():
            v.append("v")

    @rx.event
    def via_items(self):
        for k, v in self.d.items():
            v.append(k)

    @rx.event
    def via_setitem(self):
        self.d["a"] = [*self.d["a"], "s"]


def dictviews() -> rx.Component:
    return rx.vstack(
        rx.text("summary=", rx.el.span(DState.summary, id="summary")),
        rx.text("d=", rx.el.span(DState.d.to_string(), id="d")),
        rx.button("via values", id="values", on_click=DState.via_values),
        rx.button("via items", id="items", on_click=DState.via_items),
        rx.button("via setitem", id="setitem", on_click=DState.via_setitem),
    )


app = rx.App()
app.add_page(lambda: rx.text("home"), route="/", title="home")
app.add_page(filtered, route="/filtered")
app.add_page(onload, route="/onload", on_load=[LoadState.start_bg, LoadState.slow_load])
app.add_page(onload, route="/onload_plain", on_load=LoadState.plain_slow_load)
app.add_page(onload, route="/onload_bg", on_load=LoadState.bg_from_load)
app.add_page(expire, route="/expire", on_load=ExpState.on_load_count)
app.add_page(dictviews, route="/dictviews")


class FEState(rx.State):
    """Pre-existing on 0.10.0: a foreach loop var used as an on_submit partial arg -> `it_rx_state_ is not defined`."""

    items: list[str] = ["alpha", "beta"]
    got: str = ""

    @rx.event
    def store(self, which: str, form_data: dict):
        self.got = f"{which}:{form_data.get('v')}"


def foreach_arg() -> rx.Component:
    return rx.vstack(
        rx.el.span(FEState.got, id="got"),
        rx.foreach(
            FEState.items,
            lambda it: rx.form(rx.input(name="v", default_value=it), rx.button("go", type="submit"), on_submit=FEState.store("item_" + it)),
        ),
    )


app.add_page(foreach_arg, route="/foreach_arg")
