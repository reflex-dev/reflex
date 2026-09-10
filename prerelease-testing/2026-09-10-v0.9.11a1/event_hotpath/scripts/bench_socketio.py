"""A/B throughput + latency bench against a running reflex backend via python-socketio.

Speaks the same wire protocol as the compiled frontend (.web/utils/state.js):
  connect  : io("http://host:port/_event", {path: "/_event", query: {token}})  => namespace "/_event"
  send     : emit("event", {token, name, payload, router_data})
  receive  : "event" -> {delta: {state_full_name: {var: value}}, events: [...], final: bool}
  ping     : emit("ping") -> server emits "ping" with "pong"

Usage (driver venv):
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python bench_socketio.py \
      --url http://localhost:8180 --names names.json --server-pid <pid> --out result.json \
      [--serial 2000] [--clients 20] [--per-client 100] [--pipelined 2000] [--rounds 2]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
import uuid

import socketio

NS = "/_event"


def cpu_tree(root_pid: int) -> tuple[float, int, list[int]]:
    """Return (cpu_seconds, rss_bytes, pids) summed over root_pid and its descendants."""
    procs: dict[int, tuple[int, int, int]] = {}
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/stat") as f:
                s = f.read()
        except OSError:
            continue
        rest = s[s.rindex(")") + 2:].split()
        procs[int(d)] = (int(rest[1]), int(rest[11]) + int(rest[12]), int(rest[21]))
    tree = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, (ppid, _, _) in procs.items():
            if ppid in tree and pid not in tree:
                tree.add(pid)
                changed = True
    ticks = sum(procs[p][1] for p in tree if p in procs)
    rss = sum(procs[p][2] for p in tree if p in procs) * os.sysconf("SC_PAGE_SIZE")
    return ticks / os.sysconf("SC_CLK_TCK"), rss, sorted(tree)


class Client:
    def __init__(self, url: str, names: dict):
        self.url = url
        self.names = names
        self.token = str(uuid.uuid4())
        self.sio = socketio.AsyncClient(reconnection=False)
        self.updates: asyncio.Queue = asyncio.Queue()
        self.pongs: asyncio.Queue = asyncio.Queue()
        self.raw_first: list = []
        self.sio.on("event", self._on_event, namespace=NS)
        self.sio.on("ping", self._on_ping, namespace=NS)
        self.sio.on("disconnect", self._on_disc, namespace=NS)
        self.disconnected = False

    async def _on_event(self, data):
        if len(self.raw_first) < 3:
            self.raw_first.append(data)
        self.updates.put_nowait(data)

    async def _on_ping(self, data):
        self.pongs.put_nowait((time.perf_counter(), data))

    async def _on_disc(self, *a):
        self.disconnected = True

    async def connect(self):
        await self.sio.connect(
            f"{self.url}?token={self.token}", socketio_path="/_event", namespaces=[NS],
            transports=["websocket"], wait_timeout=20,
        )

    def ev(self, name: str, payload: dict | None = None) -> dict:
        return {"token": self.token, "name": name, "payload": payload or {},
                "router_data": {"pathname": "/", "asPath": "/"}}

    async def emit(self, name: str, payload: dict | None = None):
        await self.sio.emit("event", self.ev(name, payload), namespace=NS)

    def count_from(self, upd) -> int | None:
        d = upd.get("delta") or {}
        s = d.get(self.names["counter"])
        if s:
            # 0.9.x wire format suffixes var names with `_rx_state_`
            for k in ("count_rx_state_", "count"):
                if k in s:
                    return s[k]
        return None

    async def wait_count(self, target: int, timeout: float = 30.0) -> tuple[int, int]:
        """Drain updates until count == target; return (n_updates_seen, last_count)."""
        n = 0
        last = None
        while True:
            upd = await asyncio.wait_for(self.updates.get(), timeout)
            n += 1
            c = self.count_from(upd)
            if c is not None:
                last = c
                if c == target:
                    return n, c
                if c > target:
                    raise AssertionError(f"count overshoot: got {c} expected {target}")

    async def ping(self, timeout=10.0) -> float:
        t0 = time.perf_counter()
        await self.sio.emit("ping", namespace=NS)
        t1, data = await asyncio.wait_for(self.pongs.get(), timeout)
        assert data == "pong", data
        return t1 - t0

    async def close(self):
        await self.sio.disconnect()


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def stats(lat: list[float]) -> dict:
    return {"n": len(lat), "p50_ms": round(pct(lat, 50) * 1e3, 3), "p90_ms": round(pct(lat, 90) * 1e3, 3),
            "p99_ms": round(pct(lat, 99) * 1e3, 3), "max_ms": round(max(lat) * 1e3, 3),
            "mean_ms": round(statistics.fmean(lat) * 1e3, 3)}


async def serial(url, names, n, pid, label) -> dict:
    c = Client(url, names)
    await c.connect()
    await c.emit(names["reset_count"])
    await c.wait_count(0) if False else None
    # reset produces a delta only if count != 0; on a fresh token it is 0 already => no update. Use a probe:
    await c.emit(names["increment"]); await c.wait_count(1)
    lat = []
    cpu0, _, _ = cpu_tree(pid)
    t0 = time.perf_counter()
    for i in range(2, n + 2):
        s = time.perf_counter()
        await c.emit(names["increment"])
        nupd, cnt = await c.wait_count(i)
        lat.append(time.perf_counter() - s)
        if nupd != 1:
            print(f"  [{label}] serial: {nupd} updates for one event at i={i}", flush=True)
    wall = time.perf_counter() - t0
    cpu1, rss, pids = cpu_tree(pid)
    final = cnt
    await c.close()
    return {"mode": f"serial_{n}", "label": label, "wall_s": round(wall, 3), "ev_per_s": round(n / wall, 1),
            "server_cpu_s": round(cpu1 - cpu0, 3), "server_cpu_us_per_event": round((cpu1 - cpu0) / n * 1e6, 1),
            "rss_mb": round(rss / 1e6, 1), "pids": pids, "final_count": final, "expected_count": n + 1,
            "exact": final == n + 1, **stats(lat), "raw_first_update": c.raw_first[:1]}


async def concurrent(url, names, clients, per_client, pid, label) -> dict:
    cs = [Client(url, names) for _ in range(clients)]
    await asyncio.gather(*(c.connect() for c in cs))
    lat_all: list[float] = []
    finals = []

    async def run(c: Client):
        lat = []
        for i in range(1, per_client + 1):
            s = time.perf_counter()
            await c.emit(names["increment"])
            nupd, cnt = await c.wait_count(i)
            lat.append(time.perf_counter() - s)
        finals.append(cnt)
        lat_all.extend(lat)

    cpu0, _, _ = cpu_tree(pid)
    t0 = time.perf_counter()
    await asyncio.gather(*(run(c) for c in cs))
    wall = time.perf_counter() - t0
    cpu1, rss, pids = cpu_tree(pid)
    await asyncio.gather(*(c.close() for c in cs))
    total = clients * per_client
    return {"mode": f"concurrent_{clients}x{per_client}", "label": label, "wall_s": round(wall, 3),
            "ev_per_s": round(total / wall, 1), "server_cpu_s": round(cpu1 - cpu0, 3),
            "server_cpu_us_per_event": round((cpu1 - cpu0) / total * 1e6, 1), "rss_mb": round(rss / 1e6, 1),
            "finals": sorted(set(finals)), "exact": all(f == per_client for f in finals) and len(finals) == clients,
            **stats(lat_all)}


async def pipelined(url, names, n, pid, label) -> dict:
    c = Client(url, names)
    await c.connect()
    cpu0, _, _ = cpu_tree(pid)
    t0 = time.perf_counter()
    for _ in range(n):
        await c.emit(names["increment"])
    t_sent = time.perf_counter() - t0
    nupd, cnt = await c.wait_count(n, timeout=120)
    wall = time.perf_counter() - t0
    cpu1, rss, _ = cpu_tree(pid)
    await c.close()
    return {"mode": f"pipelined_{n}", "label": label, "wall_s": round(wall, 3), "send_s": round(t_sent, 3),
            "ev_per_s": round(n / wall, 1), "server_cpu_s": round(cpu1 - cpu0, 3),
            "server_cpu_us_per_event": round((cpu1 - cpu0) / n * 1e6, 1), "rss_mb": round(rss / 1e6, 1),
            "updates_received": nupd, "final_count": cnt, "exact": cnt == n and nupd == n}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--names", required=True)
    ap.add_argument("--server-pid", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--serial", type=int, default=2000)
    ap.add_argument("--clients", type=int, default=20)
    ap.add_argument("--per-client", type=int, default=100)
    ap.add_argument("--pipelined", type=int, default=2000)
    ap.add_argument("--rounds", type=int, default=2)
    a = ap.parse_args()
    names = json.load(open(a.names))
    results = {"label": a.label, "url": a.url, "names": names, "runs": []}
    # warmup
    w = await serial(a.url, names, 200, a.server_pid, a.label + "-warmup")
    print("warmup", json.dumps({k: w[k] for k in ("ev_per_s", "p50_ms", "exact", "raw_first_update")}), flush=True)
    results["warmup"] = w
    for r in range(a.rounds):
        for fn, args in ((serial, (a.serial,)), (concurrent, (a.clients, a.per_client)), (pipelined, (a.pipelined,))):
            res = await fn(a.url, names, *args, a.server_pid, a.label)
            res["round"] = r
            results["runs"].append(res)
            print(json.dumps({k: v for k, v in res.items() if k not in ("raw_first_update", "pids")}), flush=True)
            await asyncio.sleep(0.5)
    json.dump(results, open(a.out, "w"), indent=1, default=str)
    bad = [r for r in results["runs"] if not r["exact"]]
    print(f"DONE {a.label}: {len(results['runs'])} runs, {len(bad)} inexact")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    asyncio.run(main())
