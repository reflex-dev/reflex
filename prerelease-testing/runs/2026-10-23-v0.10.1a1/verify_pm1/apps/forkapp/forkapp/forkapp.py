"""QA app for #7079 / #7113 (process_model, 0.10.1a1): fork-safety of things real apps do at import time.

Module import (which 0.10.1a1 now does ONCE in the prod supervisor before forking workers) starts a
thread and a Timer, opens a logging FileHandler and a QueueListener thread, creates an SQLAlchemy
engine via rx.session() and queries it, creates httpx/asyncio objects, a sync Redis client (pinged),
and records module-level random / uuid / secrets values. /api/whoami reports what every worker sees.
"""

import asyncio
import gc
import logging
import logging.handlers
import multiprocessing
import os
import queue
import random
import secrets
import threading
import time
import uuid

import httpx
import reflex as rx
from sqlmodel import select
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

if os.environ.get("EXPECT_VENV"):  # venv guard
    assert f"/envs/{os.environ['EXPECT_VENV']}/" in rx.__file__, rx.__file__

IMPORT_PID = os.getpid()
IMPORT_PPID = os.getppid()
IMPORT_TIME = time.time()
MODULE_RANDOM = random.random()
MODULE_UUID = str(uuid.uuid4())
MODULE_TOKEN = secrets.token_hex(8)
START_METHOD_AT_IMPORT = multiprocessing.get_start_method(allow_none=True)
PRNG = random.Random()  # a user-created instance: NOT reseeded by CPython's at-fork hook
TICKS = {"n": 0, "pid": None}
TIMER = {"n": 0, "pid": None}
LIFESPAN = {"ran": 0, "pid": None, "loop_ticks": 0}
_import_log_path = os.environ.get("FORKAPP_LOG", os.path.abspath("forkapp.log"))


def _ticker():
    while True:
        TICKS["n"] += 1
        TICKS["pid"] = os.getpid()
        time.sleep(0.2)


_ticker_thread = threading.Thread(target=_ticker, daemon=True, name="forkapp-ticker")
_ticker_thread.start()


def _timer_cb():
    TIMER["n"] += 1
    TIMER["pid"] = os.getpid()
    t = threading.Timer(0.5, _timer_cb)
    t.daemon = True
    t.start()


_t0 = threading.Timer(0.5, _timer_cb)
_t0.daemon = True
_t0.start()

# logging: direct FileHandler + QueueHandler/QueueListener (listener is a thread)
_fmt = logging.Formatter("%(asctime)s pid=%(process)d %(name)s %(message)s")
log = logging.getLogger("forkapp.direct")
log.setLevel(logging.INFO)
log.propagate = False
_fh = logging.FileHandler(_import_log_path)
_fh.setFormatter(_fmt)
log.addHandler(_fh)
_q: queue.Queue = queue.Queue()
qlog = logging.getLogger("forkapp.queued")
qlog.setLevel(logging.INFO)
qlog.propagate = False
qlog.addHandler(logging.handlers.QueueHandler(_q))
_qfh = logging.FileHandler(_import_log_path + ".q")
_qfh.setFormatter(_fmt)
_listener = logging.handlers.QueueListener(_q, _qfh)
_listener.start()
log.info("import start_method=%s", START_METHOD_AT_IMPORT)
qlog.info("import start_method=%s", START_METHOD_AT_IMPORT)


class Note(rx.Model, table=True):
    """A row written by a worker."""

    text: str
    pid: int


rx.Model.create_all()
with rx.session() as _s:
    IMPORT_DB_COUNT = len(_s.exec(select(Note)).all())  # engine pool now holds a connection pre-fork

ASYNC_CLIENT = httpx.AsyncClient(timeout=3)
ASYNC_LOCK = asyncio.Lock()
ASYNC_QUEUE: asyncio.Queue = asyncio.Queue()

REDIS_URL = os.environ.get("REFLEX_REDIS_URL")
RCLIENT = None
IMPORT_REDIS_PING = None
if REDIS_URL:
    import redis

    RCLIENT = redis.Redis.from_url(REDIS_URL)
    IMPORT_REDIS_PING = RCLIENT.ping()  # connection established pre-fork


async def lifespan_task():
    LIFESPAN["ran"] += 1
    LIFESPAN["pid"] = os.getpid()
    while True:
        LIFESPAN["loop_ticks"] += 1
        await asyncio.sleep(0.5)


def db_count() -> int:
    with rx.session() as s:
        return len(s.exec(select(Note)).all())


def _snapshot():
    return {
        "pid": os.getpid(),
        "ppid": os.getppid(),
        "import_pid": IMPORT_PID,
        "import_ppid": IMPORT_PPID,
        "imported_in_this_process": IMPORT_PID == os.getpid(),
        "module_random": MODULE_RANDOM,
        "module_uuid": MODULE_UUID,
        "module_token": MODULE_TOKEN,
        "random_now": random.random(),
        "prng_now": PRNG.random(),
        "uuid_now": str(uuid.uuid4()),
        "ticks": TICKS["n"],
        "ticks_pid": TICKS["pid"],
        "ticker_alive": _ticker_thread.is_alive(),
        "timer": TIMER["n"],
        "timer_pid": TIMER["pid"],
        "threads": sorted(t.name for t in threading.enumerate()),
        "start_method": multiprocessing.get_start_method(allow_none=True),
        "start_method_at_import": START_METHOD_AT_IMPORT,
        "lifespan": dict(LIFESPAN),
        "gc_enabled": gc.isenabled(),
        "gc_freeze_count": gc.get_freeze_count(),
        "redis_ping": RCLIENT.ping() if RCLIENT else None,
        "import_redis_ping": IMPORT_REDIS_PING,
        "import_db_count": IMPORT_DB_COUNT,
        "db_count": db_count(),
        "qlistener_alive": bool(_listener._thread and _listener._thread.is_alive()),
        "env_marker": os.environ.get("FORKAPP_MARKER"),
        "backend_port": rx.config.get_config().backend_port,
    }


async def whoami(request):
    return JSONResponse(_snapshot())


async def dbwrite(request):
    try:
        with rx.session() as s:
            s.add(Note(text=f"api-{secrets.token_hex(2)}", pid=os.getpid()))
            s.commit()
            n = len(s.exec(select(Note)).all())
        return JSONResponse({"pid": os.getpid(), "db_count": n})
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"pid": os.getpid(), "error": f"{type(e).__name__}: {e}"}, status_code=500)


async def logline(request):
    log.info("api direct marker=%s", request.query_params.get("m", ""))
    qlog.info("api queued marker=%s", request.query_params.get("m", ""))
    return JSONResponse({"pid": os.getpid()})


async def fetch_self(request):
    port = rx.config.get_config().backend_port
    r = await ASYNC_CLIENT.get(f"http://127.0.0.1:{port}/ping")
    async with ASYNC_LOCK:
        await ASYNC_QUEUE.put(1)
        await ASYNC_QUEUE.get()
    return JSONResponse({"pid": os.getpid(), "status": r.status_code, "body": r.text[:40]})


async def poke(request):
    """EVT-04: a backend-initiated delta for a client that may be held by another worker."""
    token = request.path_params["token"]
    async with app.modify_state(rx.BaseStateToken(ident=token, cls=State)) as st:  # type: ignore[arg-type]
        sub = await st.get_state(State)
        sub.poked += 1
        sub.poke_pid = os.getpid()
    return JSONResponse({"pid": os.getpid(), "token": token})


api = Starlette(
    routes=[
        Route("/api/whoami", whoami),
        Route("/api/dbwrite", dbwrite),
        Route("/api/log", logline),
        Route("/api/fetch", fetch_self),
        Route("/api/poke/{token}", poke, methods=["POST"]),
    ]
)


class State(rx.State):
    """The app state."""

    count: int = 0
    worker_pid: int = 0
    poked: int = 0
    poke_pid: int = 0
    bg_result: str = ""
    db_rows: int = 0
    token: str = ""
    fetch_result: str = ""

    @rx.event
    def on_load(self):
        self.worker_pid = os.getpid()
        self.token = self.router.session.client_token

    @rx.event
    def increment(self):
        self.count += 1
        self.worker_pid = os.getpid()

    @rx.event
    def add_note(self):
        with rx.session() as s:
            s.add(Note(text=f"ui-{self.count}", pid=os.getpid()))
            s.commit()
            self.db_rows = len(s.exec(select(Note)).all())

    @rx.event(background=True)
    async def bg(self):
        await asyncio.sleep(1.0)
        async with self:
            self.bg_result = f"bg-done pid={os.getpid()} ticks={TICKS['n']}"

    @rx.event
    async def fetch(self):
        port = rx.config.get_config().backend_port
        r = await ASYNC_CLIENT.get(f"http://127.0.0.1:{port}/api/whoami")
        self.fetch_result = f"fetch {r.status_code} pid={r.json()['pid']}"


def index() -> rx.Component:
    return rx.container(
        rx.vstack(
            rx.heading("forkapp", id="title"),
            rx.text("count: ", State.count, id="count"),
            rx.text("pid: ", State.worker_pid, id="pid"),
            rx.text("poked: ", State.poked, " by ", State.poke_pid, id="poked"),
            rx.text("bg: ", State.bg_result, id="bg"),
            rx.text("rows: ", State.db_rows, id="rows"),
            rx.text("fetch: ", State.fetch_result, id="fetch"),
            rx.text("token: ", State.token, id="token"),
            rx.button("inc", on_click=State.increment, id="inc"),
            rx.button("note", on_click=State.add_note, id="note"),
            rx.button("bg", on_click=State.bg, id="bgbtn"),
            rx.button("fetch", on_click=State.fetch, id="fetchbtn"),
            spacing="2",
        )
    )


app = rx.App(api_transformer=api)
app.add_page(index, on_load=State.on_load)
app.register_lifespan_task(lifespan_task)
