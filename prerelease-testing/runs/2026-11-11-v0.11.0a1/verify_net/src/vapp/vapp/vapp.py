"""verify_net probe app. VN_VENV must name the venv whose reflex is imported."""

import os

import reflex as rx

VENV = os.environ.get("VN_VENV", "")
assert VENV and f"/envs/{VENV}/" in rx.__file__, (VENV, rx.__file__)


class S(rx.State):
    count: int = 0

    @rx.event
    def inc(self):
        self.count += 1


def index():
    return rx.vstack(
        rx.heading("vapp"),
        rx.text("count=", S.count, id="count"),
        rx.button("inc", on_click=S.inc, id="inc"),
    )


def foo_upper():
    return rx.text("Foo-upper page", id="mark")


def foo_lower():
    return rx.text("foo-lower page", id="mark")


app = rx.App()
app.add_page(index)
if os.environ.get("VN_CASE_DUP"):
    app.add_page(foo_upper, route="/Foo", on_load=rx.console_log("onload-Foo-upper"))
    app.add_page(foo_lower, route="/foo", on_load=rx.console_log("onload-foo-lower"))


# VN_TX: lifespan + api_transformer variants (issue 5).
#   fastapi       -> api_transformer=fastapi_app
#   old_mw        -> [fastapi_app, add_logging_middleware] with scope["path"] (docs @ v0.10.1)
#   new_mw        -> [fastapi_app, add_logging_middleware] with scope.get("path") (docs @ v0.11.0a1)
#   http_only_mw  -> [fastapi_app, mw that returns early for non-http scopes]
TX = os.environ.get("VN_TX")
if TX:
    from contextlib import asynccontextmanager

    from fastapi import FastAPI, Request

    LIFESPAN_LOG: list[str] = []

    @asynccontextmanager
    async def lifespan(fa: FastAPI):
        LIFESPAN_LOG.append("fastapi-start")
        print("VN_MARK fastapi lifespan start", flush=True)
        fa.state.greeting = "hello"
        yield {"client": "connected"}
        LIFESPAN_LOG.append("fastapi-stop")
        print("VN_MARK fastapi lifespan stop", flush=True)

    fastapi_app = FastAPI(lifespan=lifespan)

    @fastapi_app.get("/api/greeting")
    async def greeting(request: Request):
        return dict(
            greeting=getattr(request.app.state, "greeting", None),
            client=getattr(request.state, "client", None),
        )

    def old_mw(asgi):
        async def middleware(scope, receive, send):
            path = scope["path"]
            print("Request:", path)
            await asgi(scope, receive, send)

        return middleware

    def new_mw(asgi):
        async def middleware(scope, receive, send):
            path = scope.get("path")
            if path is not None:
                print("Request:", path)
            await asgi(scope, receive, send)

        return middleware

    def http_only_mw(asgi):
        async def middleware(scope, receive, send):
            if scope["type"] not in ("http", "websocket"):
                return
            await asgi(scope, receive, send)

        return middleware

    app.api_transformer = {
        "fastapi": fastapi_app,
        "old_mw": [fastapi_app, old_mw],
        "new_mw": [fastapi_app, new_mw],
        "http_only_mw": [fastapi_app, http_only_mw],
    }[TX]
