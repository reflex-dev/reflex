"""redis_runtime lock/cancellation test app (reflex 0.11.0a1 vs 0.10.1)."""

import asyncio
import os
import time
from typing import Any

import redis as sync_redis
import reflex as rx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

_EXPECT = os.environ.get("EXPECT_VENV")
if _EXPECT:
    assert f"/envs/{_EXPECT}/" in rx.__file__, rx.__file__

# Per-worker test hooks, armed through the /api routes (same worker as the bg task only
# if the request lands there; the drivers arm through the event instead).
ARM: dict[str, Any] = {"boom": 0, "pause_ms": 0}
TASKS: dict[str, asyncio.Task] = {}
RESULTS: dict[str, Any] = {}


def _boom_factory():
    if ARM["boom"] > 0:
        ARM["boom"] -= 1
        raise RuntimeError("armed: loading Other failed")
    return Bomb()


class Bomb:
    """Backend value whose UNPICKLING fails when armed (copies never fail)."""

    def __reduce__(self):
        return (_boom_factory, ())

    def __deepcopy__(self, memo):
        return Bomb()


def _trig_factory():
    if ARM["pause_ms"] > 0:
        ms, ARM["pause_ms"] = ARM["pause_ms"], 0
        url = os.environ.get("REFLEX_REDIS_URL")
        if url:
            sync_redis.Redis.from_url(url).execute_command("CLIENT", "PAUSE", ms, "ALL")
            ARM["paused_at"] = time.time()
    return Trig()


class Trig:
    """Backend value whose unpickling pauses redis when armed (opens a cancel window)."""

    def __reduce__(self):
        return (_trig_factory, ())

    def __deepcopy__(self, memo):
        return Trig()


class Other(rx.State):
    v: int = 0
    _bomb: Any = Bomb()


class Counter(rx.State):
    count: int = 0
    bg_count: int = 0
    api_count: int = 0
    last_pid: str = ""
    sup_calls: int = 0
    sup_progress: int = 0
    sup_done: int = 0
    r1: int = 0
    r2: int = 0
    linked_status: str = "idle"
    slow_done: int = 0
    _trig: Any = Trig()

    @rx.var
    def pid_now(self) -> str:
        return self.last_pid

    @rx.event
    def incr(self):
        self.count += 1
        self.last_pid = str(os.getpid())

    @rx.event
    async def incr_async(self, ms: int = 0):
        await asyncio.sleep(ms / 1000)
        self.count += 1
        self.last_pid = str(os.getpid())

    @rx.event
    async def slow(self, ms: int = 3000):
        await asyncio.sleep(ms / 1000)
        self.slow_done += 1

    @rx.event(background=True)
    async def bg_incr(self, n: int = 50, delay_ms: int = 20):
        for _ in range(n):
            async with self:
                self.count += 1
                self.bg_count += 1
            await asyncio.sleep(delay_ms / 1000)

    @rx.event(supersedes=True)
    async def sup(self, ms: int = 300):
        self.sup_calls += 1
        for _ in range(5):
            self.sup_progress += 1
            yield
            await asyncio.sleep(ms / 1000)
        self.sup_done += 1

    @rx.event
    async def raise_mid(self):
        self.r1 += 1
        yield
        self.r2 += 1
        raise ValueError("boom mid-yield (expected)")

    @rx.event(background=True)
    async def linked(self, mode: str = "fail", pause_ms: int = 3000):
        """#7738: enter a linked proxy from get_state; mode fail|cancel|ok.

        After a failure/cancel the task does NOT touch `self` again (that would re-enter and release the
        parent proxy and mask the bug); the outcome goes to RESULTS, read through /api/linked.
        """
        async with self:
            other = await self.get_state(Other)
            other.v += 1  # touch Other so it is saved (with its Bomb) and must be unpickled on the next load
            self.linked_status = f"start:{mode}"
            token = self.router.session.client_token
        TASKS[token] = asyncio.current_task()
        RESULTS[token] = {"mode": mode, "status": "entering", "t": time.time()}
        if mode in ("fail", "fail_hold"):
            ARM["boom"] = 1
        elif mode == "cancel":
            ARM["pause_ms"] = pause_ms
        try:
            async with other:
                other.v += 1
        except asyncio.CancelledError:
            RESULTS[token] = {"mode": mode, "status": "cancelled", "t": time.time(), "paused_at": ARM.get("paused_at")}
            raise
        except Exception as e:  # noqa: BLE001
            import traceback
            RESULTS[token] = {"mode": mode, "status": f"error:{type(e).__name__}:{e}", "t": time.time(), "tb": traceback.format_exc()[-1500:]}
            if mode == "fail_hold":
                # A long-running task that survives the error (e.g. a retry loop) keeps `other` referenced.
                await asyncio.sleep(20)
            return
        finally:
            ARM["boom"] = 0
            TASKS.pop(token, None)
        RESULTS[token] = {"mode": mode, "status": "ok", "t": time.time()}
        async with self:
            self.linked_status = f"ok:{mode}"

    @rx.event
    def arm(self, what: str, n: int):
        ARM[what] = n


def index():
    return rx.vstack(
        rx.heading("lockapp"),
        rx.text("count=", rx.text.span(Counter.count, id="count")),
        rx.text("bg=", rx.text.span(Counter.bg_count, id="bg_count")),
        rx.text("api=", rx.text.span(Counter.api_count, id="api_count")),
        rx.text("pid=", rx.text.span(Counter.pid_now, id="pid")),
        rx.text(
            "sup calls/progress/done=",
            rx.text.span(Counter.sup_calls, id="sup_calls"),
            "/",
            rx.text.span(Counter.sup_progress, id="sup_progress"),
            "/",
            rx.text.span(Counter.sup_done, id="sup_done"),
        ),
        rx.text("r1/r2=", rx.text.span(Counter.r1, id="r1"), "/", rx.text.span(Counter.r2, id="r2")),
        rx.text("linked=", rx.text.span(Counter.linked_status, id="linked")),
        rx.text("other.v=", rx.text.span(Other.v, id="other_v")),
        rx.text("slow_done=", rx.text.span(Counter.slow_done, id="slow_done")),
        rx.hstack(
            rx.button("incr", id="incr", on_click=Counter.incr),
            rx.button("incr_async", id="incr_async", on_click=Counter.incr_async(0)),
            rx.button("bg", id="bg", on_click=Counter.bg_incr(50, 20)),
            rx.button("sup", id="sup", on_click=Counter.sup(300)),
            rx.button("raise", id="raise", on_click=Counter.raise_mid),
            rx.button("slow", id="slow", on_click=Counter.slow(3000)),
            rx.button("linked fail", id="linked_fail", on_click=Counter.linked("fail", 0)),
            rx.button("linked cancel", id="linked_cancel", on_click=Counter.linked("cancel", 3000)),
            rx.button("linked ok", id="linked_ok", on_click=Counter.linked("ok", 0)),
            wrap="wrap",
        ),
        rx.link("other page", href="/other", id="nav_other"),
    )


def other_page():
    return rx.vstack(rx.text("other page"), rx.link("home", href="/", id="nav_home"))


def _token_of(request: Request) -> rx.BaseStateToken:
    return rx.BaseStateToken(ident=request.query_params["token"], cls=Counter)


async def api_bump(request: Request):
    n = int(request.query_params.get("n", "1"))
    t0 = time.monotonic()
    async with app.modify_state(_token_of(request)) as st:
        c = st if isinstance(st, Counter) else await st.get_state(Counter)
        c.count += n
        c.api_count += n
    _ms = (time.monotonic() - t0) * 1000
    if _ms > 500:
        print(f"RDS_SLOW_BUMP pid={os.getpid()} ms={_ms:.0f} start={time.time() - _ms / 1000:.3f} end={time.time():.3f}", flush=True)
    return JSONResponse({"pid": os.getpid(), "ms": (time.monotonic() - t0) * 1000})


async def api_get(request: Request):
    # Locked read (modify_state without changes): with REFLEX_OPLOCK_ENABLED a lease keeps the latest
    # state in the holder's memory, so an unlocked state_manager.get_state() can read a stale redis copy.
    if request.query_params.get("unlocked"):
        st = await app.state_manager.get_state(_token_of(request))
        c = st if isinstance(st, Counter) else await st.get_state(Counter)
        o = await st.get_state(Other)
        return _get_json(c, o)
    async with app.modify_state(_token_of(request)) as st:
        c = st if isinstance(st, Counter) else await st.get_state(Counter)
        o = await c.get_state(Other)
        return _get_json(c, o)


def _get_json(c, o):
    return JSONResponse({
        "pid": os.getpid(),
        **{k: getattr(c, k) for k in ("count", "bg_count", "api_count", "sup_calls", "sup_progress", "sup_done", "r1", "r2", "linked_status", "slow_done")},
        "other_v": o.v,
    })


async def api_cancel(request: Request):
    t = TASKS.pop(request.query_params["token"], None)
    if t is None:
        return JSONResponse({"pid": os.getpid(), "cancelled": False})
    t.cancel()
    return JSONResponse({"pid": os.getpid(), "cancelled": True})


async def api_linked(request: Request):
    return JSONResponse({"pid": os.getpid(), "result": RESULTS.get(request.query_params["token"]), "paused_at": ARM.get("paused_at")})


async def api_pid(request: Request):
    return JSONResponse({"pid": os.getpid()})


async def api_iid(request: Request):
    sm = app.state_manager
    tm = app.event_namespace._token_manager if app.event_namespace else None
    return JSONResponse({"pid": os.getpid(), "state_manager_instance_id": getattr(sm, "_instance_id", None), "token_manager_instance_id": getattr(tm, "instance_id", None)})


api = Starlette(
    routes=[
        Route("/api/bump", api_bump, methods=["POST"]),
        Route("/api/get", api_get),
        Route("/api/cancel", api_cancel, methods=["POST"]),
        Route("/api/pid", api_pid),
        Route("/api/iid", api_iid),
        Route("/api/linked", api_linked),
    ]
)

app = rx.App(api_transformer=api)
app.add_page(index, route="/")
app.add_page(other_page, route="/other")


# verify_rds: TEST-ONLY experiment (not a fix): with RDS_PATCH_SREM=1, only SREM this instance from
# `<lock>_waiters` when the exiting waiter is its last local waiter on that lock.
if os.environ.get("RDS_PATCH_SREM") == "1":
    import contextlib as _cl

    from reflex.istate.manager.redis import StateManagerRedis as _SMR

    @_cl.asynccontextmanager
    async def _request_lock_release(self, lock_key, lock_id):
        if not self._oplock_enabled:
            yield
            return
        await self._register_lock_contender(lock_key)
        try:
            yield
        finally:
            if self._n_lock_waiters(lock_key) <= 1:
                await self.redis.srem(lock_key + b"_waiters", self._instance_id)

    _SMR._request_lock_release = _request_lock_release
    print("RDS_PATCH_SREM applied", flush=True)


# verify_rds: TEST-ONLY log tagging: prefix every log record with the worker pid and api request id.
if os.environ.get("RDS_LOG_PID") == "1":
    import logging as _lg

    _old_factory = _lg.getLogRecordFactory()

    def _factory(*args, **kwargs):
        rec = _old_factory(*args, **kwargs)
        try:
            tn = asyncio.current_task().get_name()[:40]
        except Exception:  # noqa: BLE001
            tn = "-"
        rec.msg = f"[pid={os.getpid()} t={time.time():.3f} task={tn}] {rec.msg}"
        return rec

    _lg.setLogRecordFactory(_factory)
