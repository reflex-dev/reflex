"""Server-only round trip: python socket.io client -> Reflex backend, vs bare socket.io echo."""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import threading
import time
import uuid
from pathlib import Path

import socketio
import uvicorn

sys.path.insert(0, str(Path(__file__).parent))
from latency_app import BenchApp

from reflex.testing import AppHarness

HERE = Path(__file__).parent
N = 200


def med(xs):
    return round(statistics.median(xs), 2)


def p90(xs):
    xs = sorted(xs)
    return round(xs[int(len(xs) * 0.9)], 2)


async def reflex_client(port: int, inc_name: str):
    token = str(uuid.uuid4())
    sio = socketio.AsyncClient()
    got = asyncio.Queue()

    async def on_event(data):
        await got.put((time.perf_counter(), data))

    sio.on("event", handler=on_event, namespace="/_event")
    last: dict[str, object] = {}

    await sio.connect(
        f"http://127.0.0.1:{port}?token={token}",
        socketio_path="/_event",
        transports=["websocket"],
        namespaces=["/_event"],
    )
    router_data = {"pathname": "/", "asPath": "/"}

    async def send(name, payload=None):
        ev = {"token": token, "name": name, "router_data": router_data}
        if payload:
            ev["payload"] = payload
        t0 = time.perf_counter()
        await sio.emit("event", ev, namespace="/_event")
        t1, data = await asyncio.wait_for(got.get(), 10)
        last["data"] = data
        return (t1 - t0) * 1000, len(json.dumps(data))

    hyd_ms, hyd_bytes = await send("reflex___state____state.hydrate")
    hydrate_delta: dict[str, dict[str, object]] = last["data"]["delta"]  # type: ignore[index]
    hyd_breakdown = {
        sub: {
            k: len(json.dumps(v))
            for k, v in sorted(vals.items(), key=lambda kv: -len(json.dumps(kv[1])))[:6]
        }
        for sub, vals in hydrate_delta.items()
    }
    # drain on_load
    await asyncio.sleep(0.1)
    while not got.empty():
        got.get_nowait()
    rtts = []
    for _ in range(N):
        ms, _b = await send(inc_name)
        rtts.append(ms)
    await sio.disconnect()
    return {
        "hydrate_ms": round(hyd_ms, 2),
        "hydrate_bytes": hyd_bytes,
        "hydrate_breakdown": hyd_breakdown,
        "inc_median_ms": med(rtts),
        "inc_p90_ms": p90(rtts),
        "inc_min_ms": round(min(rtts), 2),
    }


async def echo_client(port: int):
    sio = socketio.AsyncClient()
    got = asyncio.Queue()

    async def on_event(data):
        await got.put(time.perf_counter())

    sio.on("event", handler=on_event)

    await sio.connect(
        f"http://127.0.0.1:{port}", socketio_path="/_event", transports=["websocket"]
    )
    rtts = []
    payload = {
        "token": "x",
        "name": "reflex___state____state.inc",
        "router_data": {"pathname": "/", "asPath": "/"},
    }
    for _ in range(N):
        t0 = time.perf_counter()
        await sio.emit("event", payload)
        t1 = await asyncio.wait_for(got.get(), 10)
        rtts.append((t1 - t0) * 1000)
    await sio.disconnect()
    return {
        "echo_median_ms": med(rtts),
        "echo_p90_ms": p90(rtts),
        "echo_min_ms": round(min(rtts), 2),
    }


def start_echo_server():
    sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")

    async def handle(sid, data):
        await sio.emit(
            "event", {"delta": {"reflex___state____state": {"counter": 1}}}, to=sid
        )

    sio.on("event", handler=handle)
    app = socketio.ASGIApp(sio, socketio_path="/_event")
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    )
    threading.Thread(target=server.run, daemon=True).start()
    while not (
        server.started
        and getattr(server, "servers", None)
        and server.servers[0].sockets
    ):
        time.sleep(0.05)
    return server, server.servers[0].sockets[0].getsockname()[1]


def main():
    out = {}
    echo_server, echo_port = start_echo_server()
    out["bare_socketio_echo"] = asyncio.run(echo_client(echo_port))
    echo_server.should_exit = True
    print(out, flush=True)

    root = HERE / "app_rtt"
    root.mkdir(exist_ok=True)
    harness = AppHarness.create(root=root, app_source=BenchApp)
    harness._initialize_app()
    harness._start_backend()
    sock = harness._poll_for_servers(timeout=30)
    port = sock.getsockname()[1]
    try:
        app_instance = harness.app_instance
        assert app_instance is not None
        inc_name = next(
            k
            for k in app_instance._registration_context.event_handlers
            if k.endswith(".inc")
        )
        out["inc_event_name"] = inc_name
        out["reflex_backend"] = asyncio.run(reflex_client(port, inc_name))
        # second run with warmed caches
        out["reflex_backend_warm"] = asyncio.run(reflex_client(port, inc_name))
    finally:
        harness.stop()
    (HERE / "report_server_rtt.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
