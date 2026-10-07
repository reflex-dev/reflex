"""Independent fixture for verifying claims E-1 / E-2 (handler raises -> state delta / persistence).

One root-level State `V` with a set of handlers that mutate state and then raise (or are
cancelled), plus controls.  Every handler prints an `EVV <epoch> ...` marker line to the server
log so the browser timeline can be correlated with the server side.
"""

import asyncio
import importlib.metadata
import os
import time

import reflex as rx
from reflex.app import default_backend_exception_handler

_EXPECT = os.environ.get("EVV_VENV", "")
assert _EXPECT, "EVV_VENV must name the venv this server is supposed to run from"
assert f"/envs/{_EXPECT}/" in rx.__file__, (_EXPECT, rx.__file__)
print(
    f"EVV boot reflex=={importlib.metadata.version('reflex')} file={rx.__file__} "
    f"redis_url={os.environ.get('REFLEX_REDIS_URL')!r} sm_mode={os.environ.get('REFLEX_STATE_MANAGER_MODE')!r}",
    flush=True,
)

# process-global switch so the driver can change the backend exception handler's behaviour
# at runtime (the handler is bound once at app construction)
EXC = {"mode": "default"}


def mark(msg: str) -> None:
    print(f"EVV {time.time():.3f} {msg}", flush=True)


class V(rx.State):
    status: str = "idle"
    spinner: str = "off"
    pings: int = 0
    log: list[str] = []
    other: str = "none"
    load_note: str = "none"
    mode: str = "default"
    _backend_note: str = "b0"
    echo_backend: str = ""

    @rx.event
    def ping(self):
        mark("ping")
        self.pings += 1

    @rx.event
    def flush_noop(self):
        mark("flush_noop")

    @rx.event
    def set_exc_mode(self, mode: str):
        EXC["mode"] = mode
        self.mode = mode
        mark(f"set_exc_mode {mode}")

    @rx.event
    def show_backend(self):
        self.echo_backend = self._backend_note

    # foreground handlers that raise

    @rx.event
    def direct_raise(self):
        mark("direct_raise: status=direct-partial then raise")
        self.status = "direct-partial"
        raise RuntimeError("boom direct")

    @rx.event
    async def async_raise(self):
        mark("async_raise: status=async-partial, await, raise")
        self.status = "async-partial"
        await asyncio.sleep(0.05)
        raise RuntimeError("boom async")

    @rx.event
    def raise_clean(self):
        mark("raise_clean: raise without mutating")
        raise RuntimeError("boom clean")

    @rx.event
    def backend_raise(self):
        mark("backend_raise: _backend_note=b-partial then raise")
        self._backend_note = "b-partial"
        raise RuntimeError("boom backend var")

    @rx.event
    def chain_a(self):
        mark("chain_a: status=a-ran, return chain_b")
        self.status = "a-ran"
        return V.chain_b

    @rx.event
    def chain_b(self):
        mark("chain_b: log+=B-partial then raise")
        self.log.append("B-partial")
        raise RuntimeError("boom chain_b")

    @rx.event
    def gen_raise(self):
        mark("gen_raise: status=gen-flushed, yield")
        self.status = "gen-flushed"
        yield
        mark("gen_raise: status=gen-after, log+=gen-after-log, raise")
        self.status = "gen-after"
        self.log.append("gen-after-log")
        raise RuntimeError("boom gen")

    @rx.event
    async def agen_raise(self):
        mark("agen_raise: status=agen-flushed, yield")
        self.status = "agen-flushed"
        yield
        await asyncio.sleep(0.05)
        mark("agen_raise: status=agen-after, raise")
        self.status = "agen-after"
        raise RuntimeError("boom agen")

    @rx.event
    async def spinner_finally(self):
        mark("spinner_finally: spinner=on, yield")
        self.spinner = "on"
        yield
        try:
            await asyncio.sleep(0.3)
            mark("spinner_finally: raising")
            raise RuntimeError("boom spinner")
        finally:
            mark("spinner_finally: finally -> spinner=off")
            self.spinner = "off"

    @rx.event
    def caught(self):
        mark("caught: handled exception, no propagation")
        self.status = "caught-partial"
        try:
            raise RuntimeError("handled")
        except RuntimeError:
            self.status = "caught-handled"

    # background tasks

    @rx.event(background=True)
    async def bg_raise_inside(self):
        mark("bg_raise_inside: in `async with self`: status=bg-inside-partial then raise")
        async with self:
            self.status = "bg-inside-partial"
            raise RuntimeError("boom bg inside")

    @rx.event(background=True)
    async def bg_two_blocks(self):
        mark("bg_two_blocks: block1 status=bg-block1-committed")
        async with self:
            self.status = "bg-block1-committed"
        await asyncio.sleep(0.1)
        mark("bg_two_blocks: block2 status=bg-block2-partial then raise")
        async with self:
            self.status = "bg-block2-partial"
            self.log.append("bg-2")
            raise RuntimeError("boom bg block2")

    @rx.event(background=True)
    async def bg_raise_after(self):
        mark("bg_raise_after: block status=bg-committed, then raise outside the lock")
        async with self:
            self.status = "bg-committed"
        raise RuntimeError("boom bg after")

    # superseding handlers

    @rx.event(supersedes=True)
    async def sup_same(self, label: str):
        mark(f"sup_same[{label}]: start")
        self.log.append(f"{label}:start")
        yield
        mark(f"sup_same[{label}]: after-yield")
        self.log.append(f"{label}:after-yield")
        await asyncio.sleep(2.0)
        mark(f"sup_same[{label}]: end")
        self.log.append(f"{label}:end")

    @rx.event(supersedes=True)
    async def sup_split(self, label: str):
        if label == "a":
            mark("sup_split[a]: start")
            self.log.append("a:start")
            yield
            mark("sup_split[a]: after-yield")
            self.log.append("a:after-yield")
            await asyncio.sleep(2.0)
            mark("sup_split[a]: end")
            self.log.append("a:end")
        else:
            mark("sup_split[b]: other=b-ran")
            self.other = "b-ran"

    # on_load that raises
    @rx.event
    def on_load_raises(self):
        mark("on_load_raises: load_note=load-partial then raise")
        self.load_note = "load-partial"
        raise RuntimeError("boom on_load")


def exc_handler(exception: Exception):
    mode = EXC["mode"]
    mark(f"backend_exception_handler mode={mode} exc={exception!r}")
    if mode == "default":
        return default_backend_exception_handler(exception)
    if mode == "alert":
        return rx.window_alert(f"custom alert: {exception}")
    if mode == "none":
        return None
    if mode == "chain":
        return [default_backend_exception_handler(exception), V.flush_noop]
    raise ValueError(mode)


def row(label: str, var, id_: str):
    return rx.hstack(
        rx.text(label, width="8em", size="2"),
        rx.text(var, id=id_, size="2", weight="bold"),
        spacing="3",
    )


def btn(label: str, handler, id_: str):
    return rx.button(label, on_click=handler, id=id_, size="1", variant="soft")


def state_rows():
    return rx.vstack(
        rx.hstack(
            rx.text("hydrated", width="8em", size="2"),
            rx.text(rx.cond(rx.State.is_hydrated, "yes", "no"), id="hyd", size="2", weight="bold"),
            spacing="3",
        ),
        row("status", V.status, "v-status"),
        row("spinner", V.spinner, "v-spinner"),
        row("pings", V.pings, "v-pings"),
        row("log", V.log.join(","), "v-log"),
        row("other", V.other, "v-other"),
        row("load_note", V.load_note, "v-load_note"),
        row("echo_backend", V.echo_backend, "v-echo_backend"),
        row("exc mode", V.mode, "v-mode"),
        spacing="1",
        align="start",
    )


def index():
    return rx.container(
        rx.box(height="230px"),
        rx.heading("EVV: events verification", size="4"),
        state_rows(),
        rx.divider(),
        rx.flex(
            btn("ping", V.ping, "btn-ping"),
            btn("direct raise", V.direct_raise, "btn-direct_raise"),
            btn("async raise", V.async_raise, "btn-async_raise"),
            btn("raise clean", V.raise_clean, "btn-raise_clean"),
            btn("backend raise", V.backend_raise, "btn-backend_raise"),
            btn("show backend", V.show_backend, "btn-show_backend"),
            btn("chain A->B(raise)", V.chain_a, "btn-chain_a"),
            btn("gen yield+raise", V.gen_raise, "btn-gen_raise"),
            btn("agen yield+raise", V.agen_raise, "btn-agen_raise"),
            btn("spinner finally", V.spinner_finally, "btn-spinner_finally"),
            btn("caught", V.caught, "btn-caught"),
            btn("bg raise inside", V.bg_raise_inside, "btn-bg_raise_inside"),
            btn("bg two blocks", V.bg_two_blocks, "btn-bg_two_blocks"),
            btn("bg raise after", V.bg_raise_after, "btn-bg_raise_after"),
            btn("sup same a", V.sup_same("a"), "btn-sup_same_a"),
            btn("sup same b", V.sup_same("b"), "btn-sup_same_b"),
            btn("sup split a", V.sup_split("a"), "btn-sup_split_a"),
            btn("sup split b", V.sup_split("b"), "btn-sup_split_b"),
            btn("nav /onload", rx.redirect("/onload"), "btn-nav_onload"),
            btn("exc: default", V.set_exc_mode("default"), "btn-mode_default"),
            btn("exc: alert", V.set_exc_mode("alert"), "btn-mode_alert"),
            btn("exc: none", V.set_exc_mode("none"), "btn-mode_none"),
            btn("exc: chain", V.set_exc_mode("chain"), "btn-mode_chain"),
            wrap="wrap",
            spacing="2",
        ),
        size="3",
    )


def onload_page():
    return rx.container(
        rx.box(height="230px"),
        rx.heading("EVV: on_load raises", size="4"),
        state_rows(),
        btn("ping", V.ping, "btn-ping"),
        btn("home", rx.redirect("/"), "btn-home"),
        size="3",
    )


app = rx.App(backend_exception_handler=exc_handler)
app.add_page(index, route="/", title="evv index")
app.add_page(onload_page, route="/onload", on_load=V.on_load_raises, title="evv onload")
