"""Repro app for reflex-dev/reflex#7072 / #7073: rehydrate after state eviction.

Run with REFLEX_REDIS_TOKEN_EXPIRATION=<seconds> (also drives the in-memory manager's expiry)
and optionally REFLEX_REDIS_URL=redis://localhost:<port>.

Pages: / (on_load load_index), /page-b (on_load load_b), /item/[item_id] (on_load load_item),
custom 404 (on_load load_404).

API (mounted via api_transformer):
  GET /api/runs                        -> module-level on_load run counters + log tail
  GET /api/reset                       -> zero counters
  GET /api/enqueue?token=T&event=ping  -> enqueue State.<event>() from the backend (no router_data)
  GET /api/expire?token=T              -> force-evict the token's state from the state manager
  GET /api/keys?token=T                -> list state keys for the token (redis keys+TTL, or in-memory keys)
  GET /api/kick?token=T[&mode=eio|sio] -> drop the client's websocket (eio = transport close, client reconnects)
"""

import asyncio
import time

import reflex as rx
from reflex.event import Event
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

RUNS = {"index": 0, "page-b": 0, "item": 0, "404": 0, "ping": 0, "click": 0, "hydrate_seen": 0}
LOG: list[str] = []


def _log(msg: str) -> None:
    LOG.append(f"{time.strftime('%H:%M:%S')} {msg}")
    del LOG[:-200]


class State(rx.State):
    clicks: int = 0
    pings: int = 0
    loaded_page: str = ""
    loaded_at: str = ""
    load_seq: int = 0
    bg_status: str = "idle"
    item_arg: str = ""
    name: str = rx.LocalStorage("", name="rh_name")
    flavor: str = rx.Cookie("", name="rh_flavor")

    @rx.var
    def path(self) -> str:
        return self.router.url.path

    def _loaded(self, page: str) -> None:
        RUNS[page] += 1
        self.loaded_page = page
        self.load_seq += 1
        self.loaded_at = time.strftime("%H:%M:%S")
        _log(f"on_load {page} (run #{RUNS[page]}) path={self.router.url.path}")

    @rx.event
    def load_index(self):
        self._loaded("index")

    @rx.event
    def load_b(self):
        self._loaded("page-b")

    @rx.event
    def load_item(self):
        self._loaded("item")
        self.item_arg = str(getattr(self, "item_id", "<no item_id attr>"))

    @rx.event
    def load_404(self):
        self._loaded("404")

    @rx.event
    def click(self):
        RUNS["click"] += 1
        self.clicks += 1
        _log(f"click -> clicks={self.clicks} path={self.router.url.path}")

    @rx.event
    def ping(self):
        RUNS["ping"] += 1
        self.pings += 1
        _log(f"ping -> pings={self.pings} router_data_empty={not self.router_data}")

    @rx.event(background=True)
    async def slow_bg(self, seconds: float = 12.0):
        async with self:
            self.bg_status = "started"
        await asyncio.sleep(seconds)
        async with self:
            self.bg_status = f"finished clicks_was={self.clicks}"
            self.clicks += 100

    @rx.event
    def set_name(self, value: str):
        self.name = value

    @rx.event
    def set_flavor(self, value: str):
        self.flavor = value


class OtherState(rx.State):
    """A second substate: under redis it is NOT materialized for events on State."""

    other_count: int = 0

    @rx.event
    def bump_other(self):
        self.other_count += 1
        _log(f"bump_other -> {self.other_count}")


def _sm():
    return app.state_manager


async def api_runs(_request):
    return JSONResponse({"runs": RUNS, "log": LOG[-40:]})


async def api_reset(_request):
    for k in RUNS:
        RUNS[k] = 0
    LOG.clear()
    return JSONResponse({"ok": True})


async def api_enqueue(request):
    token = request.query_params["token"]
    name = request.query_params.get("event", "ping")
    n = int(request.query_params.get("n", "1"))
    wait = request.query_params.get("wait", "1") == "1"
    spec = getattr(State, name)()
    results = []
    for _ in range(n):
        ev = Event.from_event_type(spec)[0]
        _log(f"backend enqueue {ev.name} token={token[:8]} router_data={ev.router_data}")
        fut = await app.event_processor.enqueue(token, ev)
        if wait:
            try:
                await asyncio.wait_for(fut.wait_all(), timeout=10)
                results.append("done")
            except asyncio.TimeoutError:
                results.append("timeout")
            except Exception as ex:  # noqa: BLE001
                results.append(f"error: {type(ex).__name__}: {ex}")
        else:
            results.append("queued")
    return JSONResponse({"results": results, "runs": RUNS})


async def api_expire(request):
    token = request.query_params["token"]
    sm = _sm()
    removed = []
    redis = getattr(sm, "redis", None)
    if redis is not None:
        async for key in redis.scan_iter(match=f"{token}*"):
            await redis.delete(key)
            removed.append(key.decode() if isinstance(key, bytes) else key)
    else:
        states = getattr(sm, "states", {})
        for key in list(states):
            if key.startswith(token):
                states.pop(key, None)
                removed.append(key)
    _log(f"api expire token={token[:8]} removed={len(removed)}")
    return JSONResponse({"removed": removed})


async def api_kick(request):
    """Drop the websocket of the client holding `token` (mode=eio: transport close -> client auto-reconnects;
    mode=sio: socket.io server disconnect -> client does not reconnect)."""
    token = request.query_params["token"]
    mode = request.query_params.get("mode", "eio")
    ns = app.event_namespace
    sids = [sid for sid, tok in ns.sid_to_token.items() if tok == token]
    done = []
    for sid in sids:
        if mode == "sio":
            await ns.server.disconnect(sid, namespace=ns.namespace)
        else:
            eio_sid = ns.server.manager.eio_sid_from_sid(sid, ns.namespace)
            await ns.server.eio.disconnect(eio_sid)
        done.append(sid)
    _log(f"api kick token={token[:8]} mode={mode} sids={done}")
    return JSONResponse({"kicked": done, "mode": mode})


async def api_whoami(_request):
    """Which worker answered, and its token manager identity (multi-worker diagnostics)."""
    import os
    ns = app.event_namespace
    tm = ns._token_manager
    return JSONResponse({
        "pid": os.getpid(),
        "token_manager": type(tm).__name__,
        "instance_id": getattr(tm, "instance_id", None),
        "local_tokens": [t[:8] for t in tm.token_to_socket],
    })


async def api_keys(request):
    token = request.query_params["token"]
    sm = _sm()
    redis = getattr(sm, "redis", None)
    out = {}
    if redis is not None:
        async for key in redis.scan_iter(match=f"*{token}*"):
            k = key.decode() if isinstance(key, bytes) else key
            out[k] = await redis.ttl(key)
    else:
        states = getattr(sm, "states", {})
        out = {k: "mem" for k in states if token in k}
    return JSONResponse({"manager": type(sm).__name__, "keys": out})


def shell(title: str, *extra) -> rx.Component:
    return rx.vstack(
        rx.heading(title, id="title"),
        rx.text("hydrated=", rx.State.is_hydrated.to_string(), id="hydrated"),
        rx.text("path=", State.path, id="path"),
        rx.text("loaded_page=", State.loaded_page, id="loaded_page"),
        rx.text("load_seq=", State.load_seq, id="load_seq"),
        rx.text("loaded_at=", State.loaded_at, id="loaded_at"),
        rx.text("clicks=", State.clicks, id="clicks"),
        rx.text("pings=", State.pings, id="pings"),
        rx.text("bg_status=", State.bg_status, id="bg_status"),
        rx.text("name=", State.name, id="name"),
        rx.text("flavor=", State.flavor, id="flavor"),
        rx.text("other_count=", OtherState.other_count, id="other_count"),
        rx.text("item_arg=", State.item_arg, id="item_arg"),
        rx.hstack(
            rx.button("click", id="b-click", on_click=State.click),
            rx.button("bump-other", id="b-other", on_click=OtherState.bump_other),
            rx.button("slow-bg", id="b-slowbg", on_click=State.slow_bg(12.0)),
            rx.input(placeholder="name (LocalStorage)", id="i-name", on_blur=State.set_name),
            rx.input(placeholder="flavor (Cookie)", id="i-flavor", on_blur=State.set_flavor),
            wrap="wrap",
        ),
        rx.hstack(
            rx.link("to /", href="/", id="l-index"),
            rx.link("to /page-b", href="/page-b", id="l-b"),
            rx.link("to /item/abc", href="/item/abc", id="l-item"),
            rx.link("to /nope", href="/nope", id="l-404"),
        ),
        *extra,
        spacing="2",
        padding="1em",
    )


def index() -> rx.Component:
    return shell("index")


def page_b() -> rx.Component:
    return shell("page-b")


def item() -> rx.Component:
    return shell("item")


def not_found() -> rx.Component:
    return shell("custom-404")


api = Starlette(
    routes=[
        Route("/api/runs", api_runs),
        Route("/api/reset", api_reset),
        Route("/api/enqueue", api_enqueue),
        Route("/api/expire", api_expire),
        Route("/api/keys", api_keys),
        Route("/api/kick", api_kick),
        Route("/api/whoami", api_whoami),
    ]
)
app = rx.App(api_transformer=api)
app.add_page(index, route="/", on_load=State.load_index)
app.add_page(page_b, route="/page-b", on_load=State.load_b)
app.add_page(item, route="/item/[item_id]", on_load=State.load_item)
app.add_page(not_found, route="/404", on_load=State.load_404)
