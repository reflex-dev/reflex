"""Socket-level checks for inline socket.io handlers (async_handlers=False) while a slow handler runs.

Client A: emit SlowState.slow (sleeps 5 s server-side), then ping x5 (0.4 s apart) and fast x3;
Client B: concurrently emit fast and expect an immediate delta.
Then A emits boom (raises) and fast; expects fast delta afterwards.

Usage: NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python socket_slow_test.py \
   --url http://localhost:8180 --names names.json --out result.json --label smoke
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bench_socketio import NS, Client  # noqa: E402


async def drain_until(c: Client, pred, timeout: float):
    t0 = time.perf_counter()
    seen = []
    while True:
        remaining = timeout - (time.perf_counter() - t0)
        upd = await asyncio.wait_for(c.updates.get(), remaining)
        seen.append(upd)
        if pred(upd):
            return seen, time.perf_counter() - t0


def slow_delta(names, upd, key):
    d = (upd.get("delta") or {}).get(names["slow_state"]) or {}
    return d.get(key + "_rx_state_", d.get(key))


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--names", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    names = json.load(open(a.names))
    out: dict = {"label": a.label, "checks": []}

    def check(name, ok, details):
        out["checks"].append({"name": name, "status": "pass" if ok else "fail", "details": details})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {details}", flush=True)

    A, B = Client(a.url, names), Client(a.url, names)
    await A.connect(); await B.connect()
    # baseline ping
    base_ping = [await A.ping() for _ in range(5)]
    check("socket.ping_baseline", max(base_ping) < 1.0, f"pong latencies ms={[round(x*1e3,2) for x in base_ping]}")

    t_start = time.perf_counter()
    await A.emit(names["slow"])
    await asyncio.sleep(0.2)
    pings = []
    for _ in range(5):
        pings.append(await A.ping(timeout=8))
        await asyncio.sleep(0.4)
    check("socket.ping_while_slow_handler_same_socket", max(pings) < 1.0,
          f"pong latencies during slow handler ms={[round(x*1e3,2) for x in pings]}")
    for _ in range(3):
        await A.emit(names["fast"])
    # client B must get its delta immediately
    tb = time.perf_counter()
    await B.emit(names["fast"])
    seenB, dtB = await drain_until(B, lambda u: slow_delta(names, u, "fast_count") == 1, 10)
    check("socket.other_client_not_blocked", dtB < 1.5, f"client B fast delta after {dtB*1e3:.1f} ms ({len(seenB)} updates)")
    # A: nothing yet (slow still running) -> first update should be slow_done=1, then fast_count 1,2,3 in order
    got, dt = await drain_until(A, lambda u: slow_delta(names, u, "fast_count") == 3, 15)
    elapsed = time.perf_counter() - t_start
    seq = [(slow_delta(names, u, "slow_done"), slow_delta(names, u, "fast_count")) for u in got]
    ok = seq[0][0] == 1 and [s[1] for s in seq[1:]] == [1, 2, 3] and 4.8 < elapsed < 9
    check("socket.same_client_order_after_slow", ok, f"updates(slow_done,fast_count)={seq} total {elapsed:.2f}s")
    # exception handling
    await A.emit(names["boom"])
    try:
        got, dt = await drain_until(A, lambda u: slow_delta(names, u, "boom_count") == 1, 2.5)
        boom_note = f"boom_count=1 delta arrived after {dt*1e3:.0f} ms ({len(got)} updates: {[ (u.get('delta'), u.get('events')) for u in got][:3]})"
    except asyncio.TimeoutError:
        got = []
        boom_note = "no delta at all within 2.5 s after the raising handler (pre-raise mutation dropped)"
    out["checks"].append({"name": "socket.pre_exception_mutation", "status": "info", "details": boom_note})
    print("[INFO] socket.pre_exception_mutation:", boom_note, flush=True)
    extra = [u for u in got if u.get("events")]
    await A.emit(names["fast"])
    got2, dt2 = await drain_until(A, lambda u: slow_delta(names, u, "fast_count") == 4, 10)
    check("socket.exception_then_next_event", not A.disconnected and dt2 < 2,
          f"boom delta then fast_count=4 after {dt2*1e3:.1f} ms; boom updates carried events={[u.get('events') for u in extra][:2]}")
    # A: ping still fine after exception
    p = await A.ping()
    check("socket.ping_after_exception", p < 1.0, f"{p*1e3:.2f} ms")
    await A.close(); await B.close()
    json.dump(out, open(a.out, "w"), indent=1, default=str)
    fails = [c for c in out["checks"] if c["status"] == "fail"]
    print(f"DONE {a.label}: {len(fails)} fail")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    asyncio.run(main())
