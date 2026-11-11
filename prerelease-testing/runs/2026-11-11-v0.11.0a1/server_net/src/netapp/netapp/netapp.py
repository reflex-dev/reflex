"""server_net probe app: CORS, lifespan/api_transformer, routes, blocking, big payloads.

Env knobs (all optional):
  NA_VENV   venv name that must contain the imported reflex (guard, required)
  NA_LOG    path of a JSON-lines file every lifespan/on_load/handler mark is appended to
  NA_TX     api_transformer variant: none|fastapi|fastapi_reg|starlette|callable|callable_path|
            callable_http_only|list|nested|fastapi_fail|fastapi_shutdown_fail|fastapi_onstartup
  NA_CASE_DUP=1  also add pages /Foo and /foo (case collision)
  NA_EXTRA=1     add an extra state var (changes the state schema, for #7653)
  NA_TASK_FAIL=1 a reflex lifespan task raising at startup
"""

import asyncio
import contextlib
import json
import os
import time

import reflex as rx

VENV = os.environ.get("NA_VENV", "")
assert VENV and f"/envs/{VENV}/" in rx.__file__, (VENV, rx.__file__)

LOG = os.environ.get("NA_LOG")
TX = os.environ.get("NA_TX", "none")


def mark(evt: str, **kw):
    """Append a mark to NA_LOG and print it.

    Args:
        evt: Event name.
        **kw: Extra fields.
    """
    rec = {"t": round(time.time(), 3), "pid": os.getpid(), "evt": evt, **kw}
    if LOG:
        with open(LOG, "a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
    print(f"NA_MARK {json.dumps(rec, default=str)}", flush=True)


class S(rx.State):
    count: int = 0
    loads: list[str] = []
    item_id: str = ""
    path_seen: str = ""
    big_len: int = 0
    uploaded: list[str] = []
    msg: str = ""
    stored: str = rx.LocalStorage("", name="na_big")
    if os.environ.get("NA_EXTRA"):
        extra_v2: int = 42

    @rx.event
    def inc(self):
        self.count += 1

    def _load(self, page: str):
        self.loads.append(page)
        self.path_seen = self.router.page.path
        mark(
            "onload",
            page=page,
            path=self.router.page.path,
            raw=self.router.page.raw_path,
            params=dict(self.router.page.params),
        )

    @rx.event
    def load_index(self):
        self._load("index")

    @rx.event
    def load_about(self):
        self._load("about")

    @rx.event
    def load_item(self):
        self.item_id = str(self.router.page.params.get("id", ""))
        self._load(f"item:{self.item_id}")

    @rx.event
    def load_upper(self):
        self._load("Foo-upper")

    @rx.event
    def load_lower(self):
        self._load("foo-lower")

    @rx.event
    def recv_big(self, data: str):
        self.big_len = len(data)
        mark("big", n=len(data))

    @rx.event
    async def handle_upload(self, files: list[rx.UploadFile]):
        out = rx.get_upload_dir()
        out.mkdir(parents=True, exist_ok=True)
        for f in files:
            data = await f.read()
            (out / f.name).write_bytes(data)
            self.uploaded.append(f.name)
        mark("upload", files=self.uploaded)

    @rx.event
    def dl_data(self):
        return rx.download(data="hello-from-netapp", filename="hello.txt")

    @rx.event
    def dl_uploaded(self):
        if self.uploaded:
            return rx.download(url=rx.get_upload_url(self.uploaded[-1]))
        return None

    @rx.event
    async def block_async(self):
        mark("block_async_start")
        time.sleep(2)
        self.msg = "block_async done"

    @rx.event
    def block_sync(self):
        mark("block_sync_start")
        time.sleep(1)
        self.msg = "block_sync done"

    @rx.event
    async def ok_async(self):
        await asyncio.sleep(2)
        self.msg = "ok_async done"

    @rx.event
    async def short_block(self):
        time.sleep(0.1)
        self.msg = "short_block done"

    @rx.event(background=True)
    async def cpu_bg(self):
        t0 = time.time()
        x = 0
        while time.time() - t0 < 3:
            x += 1
        async with self:
            self.msg = f"cpu_bg done {x}"


def nav():
    return rx.hstack(
        rx.link("home", href="/", id="nav-home"),
        rx.link("about", href="/about", id="nav-about"),
        rx.link("About(upper)", href="/About", id="nav-About"),
        rx.link("item A1", href="/items/A1", id="nav-item"),
        rx.link("ITEMS b2", href="/ITEMS/b2", id="nav-ITEMS"),
        rx.link("upload", href="/upload", id="nav-upload"),
        rx.link("block", href="/block", id="nav-block"),
    )


def common():
    return rx.vstack(
        nav(),
        rx.text("count=", S.count, id="count"),
        rx.button("inc", on_click=S.inc, id="inc"),
        rx.text("loads=", S.loads.to_string(), id="loads"),
        rx.text("path_seen=", S.path_seen, id="path_seen"),
        rx.text("router_path=", S.router.page.path, id="router_path"),
        rx.text("msg=", S.msg, id="msg"),
        rx.text("big_len=", S.big_len, id="big_len"),
        rx.text("stored_len=", S.stored.length(), id="stored_len"),
        rx.button(
            "big",
            on_click=S.recv_big(
                rx.Var("'x'.repeat(Number(window.__NA_BIG || 2000000))").to(str)
            ),
            id="big",
        ),
    )


def index():
    return rx.vstack(rx.heading("index", id="page"), common())


def about():
    return rx.vstack(rx.heading("about", id="page"), common())


def item():
    return rx.vstack(
        rx.heading("item", id="page"),
        rx.text("item_id=", S.item_id, id="item_id"),
        common(),
    )


def upload_page():
    return rx.vstack(
        rx.heading("upload", id="page"),
        common(),
        rx.upload(rx.text("drop"), id="up"),
        rx.button(
            "send",
            on_click=S.handle_upload(rx.upload_files(upload_id="up")),
            id="send",
        ),
        rx.text("uploaded=", S.uploaded.to_string(), id="uploaded"),
        rx.button("dl data", on_click=S.dl_data, id="dl_data"),
        rx.button("dl uploaded", on_click=S.dl_uploaded, id="dl_up"),
    )


def block_page():
    return rx.vstack(
        rx.heading("block", id="page"),
        common(),
        rx.button("block_async", on_click=S.block_async, id="block_async"),
        rx.button("block_sync", on_click=S.block_sync, id="block_sync"),
        rx.button("ok_async", on_click=S.ok_async, id="ok_async"),
        rx.button("short_block", on_click=S.short_block, id="short_block"),
        rx.button("cpu_bg", on_click=S.cpu_bg, id="cpu_bg"),
    )


@contextlib.asynccontextmanager
async def fa_lifespan(app):
    mark("fa_lifespan_start", app_type=type(app).__name__)
    try:
        app.state.greeting = "hello"
    except Exception as e:  # app may be the reflex App when registered as task
        mark("fa_lifespan_state_err", err=repr(e))
    yield {"client": "connected"}
    mark("fa_lifespan_stop")


@contextlib.asynccontextmanager
async def fa_lifespan_fail(app):
    mark("fa_lifespan_fail_start")
    raise RuntimeError("boom-in-lifespan-startup")
    yield


@contextlib.asynccontextmanager
async def fa_lifespan_shutdown_fail(app):
    mark("fa_lifespan_sdfail_start")
    yield
    mark("fa_lifespan_sdfail_stop")
    raise RuntimeError("boom-in-lifespan-shutdown")


def make_fastapi(lifespan=fa_lifespan, prefix="/api", **kw):
    from fastapi import FastAPI, Request

    fa = FastAPI(lifespan=lifespan, **kw) if lifespan else FastAPI(**kw)

    @fa.get(f"{prefix}/greet")
    async def greet(request: Request):
        return {
            "greeting": getattr(request.app.state, "greeting", None),
            "client": getattr(request.state, "client", None),
            "prefix": prefix,
        }

    @fa.post(f"{prefix}/echo")
    async def echo(request: Request):
        return {"body": (await request.body()).decode()}

    return fa


def make_starlette():
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    async def greet(request):
        return JSONResponse({
            "greeting": getattr(request.app.state, "greeting", None),
            "client": getattr(request.state, "client", None),
        })

    return Starlette(lifespan=fa_lifespan, routes=[Route("/api/greet", greet)])


def mw_pass(app):
    async def middleware(scope, receive, send):
        if scope["type"] == "lifespan":
            mark("mw_pass_lifespan_scope")
        await app(scope, receive, send)

    return middleware


def mw_path(app):
    # Old docs example: assumes every scope has a path.
    async def middleware(scope, receive, send):
        print("Request:", scope["path"])
        await app(scope, receive, send)

    return middleware


def mw_http_only(app):
    async def middleware(scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return
        await app(scope, receive, send)

    return middleware


transformer = None
if TX == "fastapi" or TX == "fastapi_reg":
    transformer = make_fastapi()
elif TX == "starlette":
    transformer = make_starlette()
elif TX == "callable":
    transformer = mw_pass
elif TX == "callable_path":
    transformer = [make_fastapi(), mw_path]
elif TX == "callable_http_only":
    transformer = [make_fastapi(), mw_http_only]
elif TX == "list":
    transformer = [make_fastapi(), mw_pass]
elif TX == "nested":
    transformer = [make_fastapi(), make_fastapi(prefix="/api2")]
elif TX == "fastapi_fail":
    transformer = make_fastapi(lifespan=fa_lifespan_fail)
elif TX == "fastapi_shutdown_fail":
    transformer = make_fastapi(lifespan=fa_lifespan_shutdown_fail)
elif TX == "fastapi_onstartup":
    transformer = make_fastapi(
        lifespan=None,
        on_startup=[lambda: mark("fa_on_startup")],
        on_shutdown=[lambda: mark("fa_on_shutdown")],
    )

app = rx.App(api_transformer=transformer) if transformer is not None else rx.App()


@app.register_lifespan_task
@contextlib.asynccontextmanager
async def rx_ctx_task(starlette_app):
    routes = [getattr(r, "path", None) for r in getattr(starlette_app, "routes", [])]
    mark("rx_task_start", starlette_type=type(starlette_app).__name__, routes=routes)
    if os.environ.get("NA_TASK_FAIL"):
        raise RuntimeError("boom-in-reflex-lifespan-task")
    yield
    mark("rx_task_stopping")
    if slow := os.environ.get("NA_SLOW_STOP"):
        await asyncio.sleep(float(slow))
    mark("rx_task_stop")


async def rx_coro_task():
    mark("rx_coro_start")
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        mark("rx_coro_cancelled")


app.register_lifespan_task(rx_coro_task)

if TX == "fastapi_reg":
    app.register_lifespan_task(fa_lifespan)

app.add_page(index, route="/", on_load=S.load_index)
app.add_page(about, route="/about", on_load=S.load_about)
app.add_page(item, route="/items/[id]", on_load=S.load_item)
app.add_page(upload_page, route="/upload")
app.add_page(block_page, route="/block")
if os.environ.get("NA_CASE_DUP"):
    app.add_page(
        lambda: rx.heading("Foo upper", id="page"), route="/Foo", on_load=S.load_upper
    )
    app.add_page(
        lambda: rx.heading("foo lower", id="page"), route="/foo", on_load=S.load_lower
    )
