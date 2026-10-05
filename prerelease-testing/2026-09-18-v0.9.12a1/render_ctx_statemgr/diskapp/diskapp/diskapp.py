"""StateManagerDisk probe app (#7159): set_state caching, debounce flush, API-route writes."""

import asyncio

import reflex as rx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

MARKER = "diskapp-v1"


class DiskState(rx.State):
    value: str = "init"
    counter: int = 0
    api_writes: int = 0

    @rx.event
    def set_value(self, v: str):
        self.value = v

    @rx.event
    def bump(self):
        self.counter += 1

    @rx.event
    async def rapid(self):
        """Set counter 20 times within ~1s in one handler with yields."""
        for i in range(1, 21):
            self.counter = i
            self.value = f"rapid-{i}"
            yield
            await asyncio.sleep(0.04)


def index() -> rx.Component:
    return rx.el.div(
        rx.el.h2("diskapp " + MARKER),
        rx.el.div("token=", rx.el.span(rx.State.router.session.client_token, id="token")),
        rx.el.div("value=", rx.el.span(DiskState.value, id="value")),
        rx.el.div("counter=", rx.el.span(DiskState.counter.to_string(), id="counter")),
        rx.el.div("api_writes=", rx.el.span(DiskState.api_writes.to_string(), id="api-writes")),
        rx.el.button("bump", on_click=DiskState.bump, id="bump"),
        rx.el.button("rapid", on_click=DiskState.rapid, id="rapid"),
        rx.el.input(value=DiskState.value, on_change=DiskState.set_value, id="value-input"),
        id="root",
        style={"padding": "10px", "font_family": "monospace"},
    )


async def api_poke(request: Request) -> JSONResponse:
    """Write to the state through app.modify_state (not via the websocket)."""
    from reflex.istate.manager.token import BaseStateToken

    token = request.query_params["token"]
    value = request.query_params.get("value", "from-api")
    legacy = request.query_params.get("legacy")
    tok = token if legacy else BaseStateToken(ident=token, cls=app._state)
    async with app.modify_state(tok) as root_state:
        substate = await root_state.get_state(DiskState)
        substate.value = value
        substate.api_writes += 1
        result = {"value": substate.value, "api_writes": substate.api_writes}
    return JSONResponse({"ok": True, **result})


async def api_peek(request: Request) -> JSONResponse:
    """Read the state through the state manager."""
    from reflex.istate.manager.token import BaseStateToken

    token = request.query_params["token"]
    sm = app.state_manager
    st = await sm.get_state(BaseStateToken(ident=token, cls=app._state))
    sub = await st.get_state(DiskState)
    return JSONResponse(
        {
            "value": sub.value,
            "counter": sub.counter,
            "api_writes": sub.api_writes,
            "manager": type(sm).__name__,
        }
    )


async def api_set_fresh(request: Request) -> JSONResponse:
    """set_state with a state instance NOT obtained from get_state (#7159)."""
    from reflex.istate.manager.token import BaseStateToken

    token_str = request.query_params["token"]
    value = request.query_params.get("value", "fresh")
    sm = app.state_manager
    token = BaseStateToken(ident=token_str, cls=app._state)
    fresh = app._state(_reflex_internal_init=True)
    sub = await fresh.get_state(DiskState)
    sub.value = value
    sub.counter = 999
    # drop touched tracking, mimicking a state built from scratch
    for s in (fresh, sub):
        s.dirty_vars.clear()
        s._was_touched = False
    await sm.set_state(token, fresh)
    return JSONResponse({"ok": True, "manager": type(sm).__name__})



async def api_disk_read(request: Request) -> JSONResponse:
    """Read DiskState straight off disk, bypassing the in-memory cache."""
    from reflex.istate.manager.token import BaseStateToken

    token_str = request.query_params["token"]
    sm = app.state_manager
    on_disk = await sm.load_state(BaseStateToken(ident=token_str, cls=DiskState))
    cached = sm.states.get(BaseStateToken(ident=token_str, cls=app._state).cache_key)
    cached_sub = None
    if cached is not None:
        try:
            cached_sub = cached.substates[DiskState.get_name()]
        except Exception:
            cached_sub = None
    return JSONResponse(
        {
            "manager": type(sm).__name__,
            "debounce": sm._write_debounce_seconds,
            "queue_len": len(sm._write_queue),
            "disk": None
            if on_disk is None
            else {"value": on_disk.value, "counter": on_disk.counter, "api_writes": on_disk.api_writes},
            "cache": None
            if cached_sub is None
            else {"value": cached_sub.value, "counter": cached_sub.counter, "api_writes": cached_sub.api_writes},
        }
    )


async def api_double_set(request: Request) -> JSONResponse:
    """Two set_state calls with DIFFERENT fresh instances inside one debounce window (#7159).

    The debounced write must flush the value supplied SECOND, not the first.
    """
    from reflex.istate.manager.token import BaseStateToken

    token_str = request.query_params["token"]
    sm = app.state_manager
    token = BaseStateToken(ident=token_str, cls=app._state)
    supplied = []
    for value, counter in (("first-queued", 101), ("second-queued", 202)):
        fresh = app._state(_reflex_internal_init=True)
        sub = await fresh.get_state(DiskState)
        sub.value = value
        sub.counter = counter
        # a state built from scratch carries no touched tracking
        for st in (fresh, sub):
            st.dirty_vars.clear()
            st._was_touched = False
        await sm.set_state(token, fresh)
        supplied.append({"value": value, "counter": counter, "queue_len": len(sm._write_queue)})
    return JSONResponse({"ok": True, "supplied": supplied})


async def api_dump(request: Request) -> JSONResponse:
    """Dump the disk manager's cache keys, queue keys and token->path mapping."""
    from reflex.istate.manager.token import BaseStateToken

    sm = app.state_manager
    token_str = request.query_params.get("token", "")
    paths = {}
    if token_str:
        for cls in (app._state, DiskState):
            t = BaseStateToken(ident=token_str, cls=cls)
            pth = sm.token_path(t)
            paths[cls.get_full_name()] = {
                "str": str(t),
                "cache_key": t.cache_key,
                "path": pth.name,
                "exists": pth.exists(),
            }
    return JSONResponse(
        {
            "cache_keys": [str(k) for k in sm.states],
            "queue_keys": [str(k) for k in sm._write_queue],
            "paths_for_token": paths,
            "states_dir": str(sm.states_directory),
            "files": sorted(p.name for p in sm.states_directory.glob("*.pkl")),
        }
    )


api = Starlette(
    routes=[
        Route("/api/poke", api_poke),
        Route("/api/peek", api_peek),
        Route("/api/set_fresh", api_set_fresh),
        Route("/api/disk_read", api_disk_read),
        Route("/api/double_set", api_double_set),
        Route("/api/dump", api_dump),
    ]
)

app = rx.App(api_transformer=api)
app.add_page(index, route="/")
