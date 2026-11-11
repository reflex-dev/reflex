"""Raw socket.io load/correctness driver for lockapp.

Usage: $SB/envs/vrds-drv/bin/python load.py BASE --clients C --events M --mode seq|pipe
          [--bg N] [--api K] [--event incr|incr_async] [--label L] [--out file.jsonl] [--timeout S]
Each client: own token; fires M Counter.incr events (seq = wait for each delta, like the frontend; pipe = all at once),
optionally starts a bg_incr(N, 5ms) background task and K concurrent POST /api/bump on the same token (these land on
any granian worker -> cross-process lock contention). Checks final count == M + N + K via /api/get.
"""
import argparse, asyncio, json, os, statistics, sys, time, uuid

import aiohttp
import socketio

assert "/envs/vrds-drv/" in sys.executable, sys.executable
CNT = "reflex___state____state.lockapp___lockapp____counter"

ap = argparse.ArgumentParser()
ap.add_argument("base"); ap.add_argument("--clients", type=int, default=4); ap.add_argument("--events", type=int, default=50)
ap.add_argument("--mode", default="seq"); ap.add_argument("--bg", type=int, default=0); ap.add_argument("--api", type=int, default=0)
ap.add_argument("--event", default="incr"); ap.add_argument("--label", default=""); ap.add_argument("--out", default="")
ap.add_argument("--timeout", type=float, default=120); ap.add_argument("--api-conc", type=int, default=4)
a = ap.parse_args()
base = a.base.rstrip("/")


async def client(idx: int, http: aiohttp.ClientSession):
    tok = str(uuid.uuid4())
    sio = socketio.AsyncClient(reconnection=False)
    state = {"count": 0, "pid": None, "errors": []}
    changed = asyncio.Condition()

    @sio.on("event", namespace="/_event")
    async def on_event(update):
        d = update.get("delta", {}).get(CNT, {})
        if "count_rx_state_" in d:
            async with changed:
                state["count"] = max(state["count"], d["count_rx_state_"])
                changed.notify_all()
        if "last_pid_rx_state_" in d:
            state["pid"] = d["last_pid_rx_state_"]
        for ev in update.get("events", []) or []:
            if "toast" in json.dumps(ev) or "error" in json.dumps(ev).lower():
                state["errors"].append(json.dumps(ev)[:300])

    await sio.connect(f"{base}?token={tok}", socketio_path="/_event", transports=["websocket"], namespaces=["/_event"])
    lat = []

    async def emit(name, payload=None):
        await sio.emit("event", {"name": f"{CNT}.{name}", "payload": payload or {}, "router_data": {"pathname": "/", "asPath": "/"}}, namespace="/_event")

    async def wait_count(target, timeout):
        async with changed:
            await asyncio.wait_for(changed.wait_for(lambda: state["count"] >= target), timeout)

    async def api_bumps():
        lat_api = []
        sem = asyncio.Semaphore(a.api_conc)
        async def one():
            async with sem:
                t0 = time.monotonic()
                async with http.post(f"{base}/api/bump?token={tok}&n=1") as r:
                    j = await r.json()
                lat_api.append((time.monotonic() - t0) * 1000)
                return j["pid"]
        pids = await asyncio.gather(*[one() for _ in range(a.api)])
        return lat_api, sorted(set(pids))

    t_start = time.monotonic()
    if a.bg:
        await emit("bg_incr", {"n": a.bg, "delay_ms": 5})
    api_task = asyncio.create_task(api_bumps()) if a.api else None
    payload = {"ms": 0} if a.event == "incr_async" else None
    timed_out = False
    try:
        if a.mode == "seq":
            for i in range(a.events):
                before = state["count"]
                t0 = time.monotonic()
                await emit(a.event, payload)
                await wait_count(before + 1, a.timeout)
                lat.append((time.monotonic() - t0) * 1000)
        else:
            for i in range(a.events):
                await emit(a.event, payload)
        api_lat, api_pids = (await api_task) if api_task else ([], [])
        await wait_count(a.events + a.bg + a.api, a.timeout)
    except (asyncio.TimeoutError, TimeoutError):
        timed_out = True
        api_lat, api_pids = ([], [])
    elapsed = time.monotonic() - t_start
    await asyncio.sleep(0.3)
    async with http.get(f"{base}/api/get?token={tok}") as r:
        final = await r.json()
    await sio.disconnect()
    exp = a.events + a.bg + a.api
    return {"client": idx, "token": tok, "expected": exp, "server_count": final["count"], "client_count": state["count"],
            "bg_count": final["bg_count"], "api_count": final["api_count"], "ok": final["count"] == exp and state["count"] == exp,
            "timed_out": timed_out, "elapsed_s": round(elapsed, 3), "lat": lat, "api_lat": api_lat, "api_pids": api_pids,
            "sock_pid": state["pid"], "errors": state["errors"][:3]}


def pct(xs, q):
    if not xs:
        return None
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * len(xs)))], 2)


async def main():
    async with aiohttp.ClientSession() as http:
        res = await asyncio.gather(*[client(i, http) for i in range(a.clients)], return_exceptions=True)
    exc = [repr(r) for r in res if isinstance(r, BaseException)]
    res = [r for r in res if not isinstance(r, BaseException)]
    lat = [x for r in res for x in r["lat"]]
    api_lat = [x for r in res for x in r["api_lat"]]
    summ = {"label": a.label, "mode": a.mode, "clients": a.clients, "events": a.events, "bg": a.bg, "api": a.api,
            "ok": sum(r["ok"] for r in res), "of": a.clients, "timeouts": sum(r["timed_out"] for r in res), "exceptions": exc,
            "p50": pct(lat, 0.5), "p90": pct(lat, 0.9), "p99": pct(lat, 0.99), "max": pct(lat, 1.0),
            "api_conc": a.api_conc, "api_over_500ms": sum(x > 500 for x in api_lat), "seq_over_500ms": sum(x > 500 for x in lat), "api_p50": pct(api_lat, 0.5), "api_p99": pct(api_lat, 0.99), "api_max": pct(api_lat, 1.0),
            "elapsed_max": max((r["elapsed_s"] for r in res), default=None),
            "bad": [{k: r[k] for k in ("client", "token", "expected", "server_count", "client_count", "bg_count", "api_count", "timed_out", "errors")} for r in res if not r["ok"]],
            "sock_pids": sorted({r["sock_pid"] for r in res if r["sock_pid"]}), "api_pids": sorted({p for r in res for p in r["api_pids"]})}
    print(json.dumps(summ))
    if a.out:
        with open(a.out, "a") as f:
            f.write(json.dumps(summ) + "\n")

asyncio.run(main())
