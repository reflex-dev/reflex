"""Malformed socket.io messages must not wedge the socket (inline handlers, async_handlers=False in 0.9.11a1).

For each bad message the client sends it, then sends a valid `increment` and expects the count delta.
Also a burst: 200 bad messages interleaved with 200 increments.

Usage: NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 $SB/envs/driver/bin/python socket_malformed_test.py \
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

BAD = [
    ("string_not_json", "this is not json"),
    ("string_json_list", json.dumps([1, 2, 3])),
    ("list_not_dict", [1, 2, 3]),
    ("int", 42),
    ("none", None),
    ("empty_dict", {}),
    ("missing_name", {"token": "T", "payload": {}, "router_data": {}}),
    ("unknown_handler", {"token": "T", "name": "no.such.state.handler", "payload": {}, "router_data": {"pathname": "/"}}),
    ("payload_not_dict", {"token": "T", "name": "INC", "payload": "oops", "router_data": {"pathname": "/"}}),
    ("payload_extra_arg", {"token": "T", "name": "INC", "payload": {"bogus": 1}, "router_data": {"pathname": "/"}}),
    ("router_data_not_dict", {"token": "T", "name": "INC", "payload": {}, "router_data": "nope"}),
    ("router_data_none", {"token": "T", "name": "INC", "payload": {}, "router_data": None}),
    ("token_mismatch", {"token": "someone-elses-token", "name": "INC", "payload": {}, "router_data": {"pathname": "/"}}),
    ("no_token", {"name": "INC", "payload": {}, "router_data": {"pathname": "/"}}),
    ("extra_fields", {"token": "T", "name": "INC", "payload": {}, "router_data": {"pathname": "/"}, "zzz": 1, "__class__": "x"}),
    ("unknown_socket_event", "__UNKNOWN_EVENT__"),
    ("no_args_event", "__NO_ARGS__"),
]


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

    c = Client(a.url, names)
    await c.connect()
    await c.emit(names["increment"])
    n, cnt = await c.wait_count(1)
    expected = 1
    for label, msg in BAD:
        if isinstance(msg, dict):
            msg = {k: (c.token if v == "T" else names["increment"] if v == "INC" else v) for k, v in msg.items()}
        t0 = time.perf_counter()
        try:
            if msg == "__UNKNOWN_EVENT__":
                await c.sio.emit("totally_unknown_event", {"a": 1}, namespace=NS)
            elif msg == "__NO_ARGS__":
                await c.sio.emit("event", namespace=NS)
            else:
                await c.sio.emit("event", msg, namespace=NS)
        except Exception as e:  # noqa: BLE001
            check(f"malformed.{label}.send", False, f"client emit raised {type(e).__name__}: {e}")
            continue
        # drain anything the bad message produced (up to 0.5 s); a "bad" message may legitimately apply (the server
        # takes the token from the socket session, not from the payload), so track the count it produced
        got = []
        try:
            while True:
                got.append(await asyncio.wait_for(c.updates.get(), 0.5))
        except asyncio.TimeoutError:
            pass
        applied = [c.count_from(u) for u in got if c.count_from(u) is not None]
        if applied:
            expected = max(expected, max(applied))
        expected += 1
        await c.emit(names["increment"])
        try:
            n, cnt = await c.wait_count(expected, timeout=5)
            dt = time.perf_counter() - t0
            check(f"malformed.{label}", not c.disconnected and cnt == expected,
                  f"count={cnt} after {dt*1e3:.0f} ms; bad msg applied_increment={bool(applied)} produced {len(got)} update(s): {json.dumps([{k: (str(v)[:160]) for k, v in u.items()} for u in got], default=str)[:420]}")
        except (asyncio.TimeoutError, AssertionError) as e:
            check(f"malformed.{label}", False, f"no/incorrect delta after bad message: {type(e).__name__}: {e}; disconnected={c.disconnected}; produced={json.dumps(got, default=str)[:300]}")
            if c.disconnected:
                break
    # burst: 200 bad + 200 good interleaved, then exact count
    if not c.disconnected:
        t0 = time.perf_counter()
        for i in range(200):
            await c.sio.emit("event", [1, 2, 3], namespace=NS)
            await c.emit(names["increment"])
        expected += 200
        try:
            n, cnt = await c.wait_count(expected, timeout=30)
            check("malformed.burst_200_bad_200_good", cnt == expected, f"final count {cnt} (expected {expected}) in {time.perf_counter()-t0:.2f}s")
        except (asyncio.TimeoutError, AssertionError) as e:
            check("malformed.burst_200_bad_200_good", False, f"{type(e).__name__}: {e}")
    p = None
    try:
        p = await c.ping()
        check("malformed.ping_after_all", p < 1.0, f"pong {p*1e3:.1f} ms; disconnected={c.disconnected}")
    except Exception as e:  # noqa: BLE001
        check("malformed.ping_after_all", False, f"{type(e).__name__}: {e}; disconnected={c.disconnected}")
    await c.close()
    json.dump(out, open(a.out, "w"), indent=1, default=str)
    fails = [x for x in out["checks"] if x["status"] == "fail"]
    print(f"DONE {a.label}: {len(fails)} fail / {len(out['checks'])}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    asyncio.run(main())
