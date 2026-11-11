"""xcut app: see rxconfig.py docstring."""

import asyncio
import contextlib
import json
import os
import time

import reflex as rx
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

import reflex_enterprise as rxe
from reflex_enterprise.auth import AuthUserState

LIFELOG = os.environ.get("XC_LIFELOG", "/dev/null")
RUNLOG = os.environ.get("XC_RUNLOG", "/dev/null")
PID = os.getpid()


def _log(path: str, **rec) -> None:
    with open(path, "a") as f:
        f.write(json.dumps({"t": round(time.time(), 3), "pid": os.getpid(), **rec}) + "\n")


class Pub(rx.State):
    """Public state: parity probes, awaited-protected calls, Redis concurrency."""

    info: rx.Field[dict[str, str]] = rxe.field(default_factory=dict, auth=False)
    awaited: rx.Field[str] = rxe.field("", auth=False)
    awaited_bg: rx.Field[str] = rxe.field("", auth=False)
    n: rx.Field[int] = rxe.field(0, auth=False)
    tags: rx.Field[list[str]] = rxe.field(default_factory=list, auth=False)
    bg: rx.Field[int] = rxe.field(0, auth=False)
    stacked_hits: rx.Field[int] = rxe.field(0, auth=False)

    @rxe.event(auth=False)
    def probe(self, via: str = "ws"):
        """Record what the handler sees of router/session/headers (no secrets copied)."""
        s = self.router.session
        h = self.router.headers
        self.info = {
            "via": via,
            "client_ip": str(s.client_ip),
            "client_token_len": str(len(s.client_token or "")),
            "session_id_set": str(bool(s.session_id)),
            "host": str(h.host),
            "origin": str(h.origin),
            "user_agent_set": str(bool(h.user_agent)),
            "cookie_len": str(len(h.cookie or "")),
            "xff": str(h.raw_headers.get("x-forwarded-for", "")),
            "page": str(self.router.url.path),
            "pid": str(os.getpid()),
        }
        _log(RUNLOG, ev="probe", **self.info)

    @rxe.event(auth=False)
    async def call_protected(self):
        """Await a protected handler from a public one (#7782)."""
        res = await Vault.secret_action()
        self.awaited = f"result={res!r}"
        _log(RUNLOG, ev="call_protected", result=repr(res))

    @rxe.event(auth=False, background=True)
    async def bg_call_protected(self):
        """Await a protected handler from a background task, outside the lock."""
        res = await Vault.secret_action()
        async with self:
            self.awaited_bg = f"result={res!r}"
        _log(RUNLOG, ev="bg_call_protected", result=repr(res))

    @rxe.event(auth=False)
    async def slow_inc(self, tag: str = "x"):
        """Read-modify-write with a sleep: lost updates show missing serialization."""
        v = self.n
        await asyncio.sleep(0.2)
        self.n = v + 1
        self.tags.append(tag)

    @rxe.event(auth=False, background=True)
    async def bg_task(self):
        """Background task incrementing under `async with self`."""
        for _ in range(10):
            async with self:
                self.bg += 1
            await asyncio.sleep(0.05)

    @rxe.event(auth=False)
    @rx.event
    def stacked(self):
        """rxe.event stacked over rx.event (rxe 0.9.11 changelog says this works)."""
        self.stacked_hits += 1

    @rxe.event(auth=False)
    def reset_all(self):
        self.n = 0
        self.tags = []
        self.bg = 0
        self.awaited = ""
        self.awaited_bg = ""


class Vault(rx.State):
    """Protected by default (AuthPlugin secure-by-default sweep)."""

    ran: rx.Field[int] = rx.field(0)

    @rxe.event
    async def secret_action(self) -> str:
        """Protected handler returning a value."""
        user = await AuthUserState.current() or {}
        self.ran += 1
        _log(RUNLOG, ev="secret_action_RAN", sub=str(user.get("sub")))
        return "secret-value-for-" + str(user.get("sub"))


@rxe.page(route="/", auth=False)
def index() -> rx.Component:
    return rx.vstack(
        rx.cond(
            AuthUserState.sub,
            rx.text("Signed in as ", AuthUserState.sub, id="signed-in"),
            rx.text("anonymous", id="anon"),
        ),
        rx.text(Pub.info.to_string(), id="info"),
        rx.text(Pub.awaited, id="awaited"),
        rx.text(Pub.awaited_bg, id="awaited-bg"),
        rx.text(Pub.n, id="n"),
        rx.text(Pub.tags.join(","), id="tags"),
        rx.text(Pub.bg, id="bg"),
        rx.text(Pub.stacked_hits, id="stacked"),
        rx.button("probe", id="probe", on_click=Pub.probe("ws")),
        rx.button("call protected", id="call-protected", on_click=Pub.call_protected),
        rx.button("bg call protected", id="bg-call-protected", on_click=Pub.bg_call_protected),
        rx.button("inc", id="inc", on_click=Pub.slow_inc("ws")),
        rx.button("bg", id="bg-start", on_click=Pub.bg_task),
        rx.button("stacked", id="stacked-btn", on_click=Pub.stacked),
        rx.button("reset", id="reset", on_click=Pub.reset_all),
        rx.link("vault", href="/vault", id="nav-vault"),
        rx.link("login", href="/login", id="nav-login"),
    )


@rxe.page(route="/vault")
def vault() -> rx.Component:
    return rx.vstack(
        rx.text("vault-content", id="vault"),
        rx.text(Vault.ran, id="ran"),
        rx.button("direct", id="direct", on_click=Vault.secret_action),
        rx.button("call protected", id="call-protected", on_click=Pub.call_protected),
        rx.text(Pub.awaited, id="awaited"),
        rx.button("logout", id="logout", on_click=AuthUserState.logout),
        rx.link("home", href="/", id="nav-home"),
    )


@contextlib.asynccontextmanager
async def user_lifespan_task(app):
    """A user lifespan task registered with register_lifespan_task."""
    _log(LIFELOG, ev="user_task_start", app_type=type(app).__name__)
    try:
        yield
    finally:
        _log(LIFELOG, ev="user_task_stop")


@contextlib.asynccontextmanager
async def transformer_lifespan(app):
    """The api_transformer Starlette app's own lifespan (#7624 now runs it)."""
    _log(LIFELOG, ev="transformer_start")
    yield {"xc_state": "from-transformer"}
    _log(LIFELOG, ev="transformer_stop")


async def hello(request):
    return JSONResponse({"hello": "xcut", "state": getattr(request.state, "xc_state", None), "pid": os.getpid()})


_mode = os.environ.get("XC_TRANSFORMER", "")
_kwargs = {}
if _mode == "starlette":
    _kwargs["api_transformer"] = Starlette(routes=[Route("/xc/hello", hello)], lifespan=transformer_lifespan)

app = rxe.App(**_kwargs)
app.register_lifespan_task(user_lifespan_task)
if _mode == "starlette" and os.environ.get("XC_REG_TWICE") == "1":
    app.register_lifespan_task(_kwargs["api_transformer"].router.lifespan_context)
_log(LIFELOG, ev="module_import")
