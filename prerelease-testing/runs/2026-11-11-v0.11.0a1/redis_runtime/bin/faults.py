"""Fault-injection scenarios for lockapp (prod + Redis, >=2 granian workers).

Usage: $SB/envs/redis_runtime-drv/bin/python faults.py BASE REDIS_PORT SCENARIO [--label L] [--out f.jsonl]
SCENARIO: lost_none | lost_kill_pubsub | lost_config_off | kill9 | redis_restart | sigstop
"""
import argparse, asyncio, json, os, signal, subprocess, sys, time, uuid

import aiohttp
import socketio

assert "/envs/redis_runtime-drv/" in sys.executable, sys.executable
CNT = "reflex___state____state.lockapp___lockapp____counter"
ap = argparse.ArgumentParser()
ap.add_argument("base"); ap.add_argument("rport"); ap.add_argument("scenario")
ap.add_argument("--label", default=""); ap.add_argument("--out", default=""); ap.add_argument("--redis-pidfile", default="")
ap.add_argument("--down", type=float, default=10.0); ap.add_argument("--fault-at", type=float, default=float(os.environ.get("FAULT_AT", "1.9")))
a = ap.parse_args()
base = a.base.rstrip("/")
T0 = time.monotonic()


def now():
    return round(time.monotonic() - T0, 3)


def rcli(*args):
    return subprocess.run(["redis-cli", "-p", a.rport, *map(str, args)], capture_output=True, text=True, timeout=30).stdout.strip()


class Client:
    def __init__(self, tok=None):
        self.tok = tok or str(uuid.uuid4())
        self.sio = socketio.AsyncClient(reconnection=False)
        self.count = None; self.pid = None; self.log = []; self.cond = asyncio.Condition(); self.new_token = None
        self.slow_done = None
        self.api_deltas = 0

        @self.sio.on("event", namespace="/_event")
        async def on_event(update):
            d = update.get("delta", {}).get(CNT, {})
            self.log.append((now(), json.dumps(update)[:200]))
            async with self.cond:
                if "api_count_rx_state_" in d:
                    self.api_deltas += 1
                if "count_rx_state_" in d:
                    self.count = d["count_rx_state_"]
                if "slow_done_rx_state_" in d:
                    self.slow_done = d["slow_done_rx_state_"]
                if "last_pid_rx_state_" in d:
                    self.pid = int(d["last_pid_rx_state_"])
                self.cond.notify_all()

        @self.sio.on("new_token", namespace="/_event")
        async def on_new_token(t):
            self.new_token = t
            self.log.append((now(), f"new_token {t}"))

        @self.sio.event(namespace="/_event")
        async def disconnect(*args):
            self.log.append((now(), f"disconnect {args}"))

    async def connect(self):
        await self.sio.connect(f"{base}?token={self.tok}", socketio_path="/_event", transports=["websocket"], namespaces=["/_event"], wait_timeout=60)

    async def emit(self, name, payload=None):
        await self.sio.emit("event", {"name": f"{CNT}.{name}", "payload": payload or {}, "router_data": {"pathname": "/", "asPath": "/"}}, namespace="/_event")

    async def wait(self, pred, timeout):
        t = time.monotonic()
        try:
            async with self.cond:
                await asyncio.wait_for(self.cond.wait_for(pred), timeout)
            return round(time.monotonic() - t, 3)
        except (asyncio.TimeoutError, TimeoutError):
            return None


async def bump(tok, timeout=40):
    t = time.monotonic()
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(force_close=True)) as s:
            async with s.post(f"{base}/api/bump?token={tok}&n=1", timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                j = await r.json()
                return {"pid": j["pid"], "s": round(time.monotonic() - t, 3), "done_at": now()}
    except Exception as e:  # noqa: BLE001
        return {"err": repr(e)[:150], "s": round(time.monotonic() - t, 3), "done_at": now()}


async def get(tok, timeout=40):
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(force_close=True)) as s:
            async with s.get(f"{base}/api/get?token={tok}", timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                return await r.json()
    except Exception as e:  # noqa: BLE001
        return {"err": repr(e)[:150]}


async def lost(mode):
    """slow(2000) holds the lock on the socket's worker; 6 api bumps on fresh connections wait for it (some on
    the other worker -> they need the pubsub release notification). Fault injected at +1.0 s."""
    c = Client(); await c.connect(); await c.emit("incr"); await c.wait(lambda: c.count == 1, 10)
    orig = rcli("CONFIG", "GET", "notify-keyspace-events").splitlines()[-1]
    t_slow = now(); await c.emit("slow", {"ms": 2000})
    await asyncio.sleep(0.3)
    tasks = [asyncio.create_task(bump(c.tok)) for _ in range(10)]
    await asyncio.sleep(a.fault_at - 0.3)
    fault = None
    if mode == "kill_pubsub":
        fault = rcli("CLIENT", "KILL", "TYPE", "pubsub")
    elif mode == "config_off":
        fault = rcli("CONFIG", "SET", "notify-keyspace-events", "")
    res = await asyncio.gather(*tasks)
    w = await c.wait(lambda: c.slow_done == 1, 20)
    rcli("CONFIG", "SET", "notify-keyspace-events", orig)
    st = await get(c.tok)
    await c.sio.disconnect()
    slow_end = t_slow + 2.0
    other = [r for r in res if r.get("pid") and r["pid"] != c.pid]
    return {"sock_pid": c.pid, "fault": fault, "orig_notify": orig, "bumps": res,
            "max_wait_after_slow_end_s": round(max(r["done_at"] for r in res) - slow_end, 3),
            "other_worker_bumps": len(other), "final_count": st.get("count"), "expected": 11, "fault_at": a.fault_at,
            "other_worker_waits": sorted(round(r["done_at"] - slow_end, 3) for r in other)}


async def kill9():
    c = Client(); await c.connect(); await c.emit("incr"); await c.wait(lambda: c.count == 1, 10)
    pid = c.pid
    await c.emit("slow", {"ms": 5000})
    await asyncio.sleep(0.5)
    t_kill = now(); os.kill(pid, signal.SIGKILL)
    await asyncio.sleep(0.5)
    lock_pttl = rcli("PTTL", f"{c.tok}_lock")
    b = asyncio.create_task(bump(c.tok, timeout=60))
    # reconnect a socket with the same token (as the browser would)
    c2 = None; reconnect = None
    for i in range(40):
        try:
            c2 = Client(c.tok); await c2.connect(); reconnect = now(); break
        except Exception as e:  # noqa: BLE001
            await asyncio.sleep(0.5)
    await c2.emit("incr")
    w = await c2.wait(lambda: c2.count is not None, 60)
    br = await b
    st = await get(c.tok)
    await c2.sio.disconnect()
    return {"killed_pid": pid, "t_kill": t_kill, "lock_pttl_after_kill_ms": lock_pttl, "reconnect_at": reconnect,
            "new_token": c2.new_token, "incr_after_reconnect_s": w, "incr_done_since_kill_s": round(now() - t_kill, 2) if w else None,
            "bump": br, "bump_since_kill_s": round(br["done_at"] - t_kill, 3), "final": {k: st.get(k) for k in ("count", "slow_done", "api_count")} if "err" not in st else st,
            "client2_log": c2.log[-5:]}


async def cross_worker_delivery(c, label):
    """10 api bumps on fresh connections (any worker); how many deltas reach the existing socket c."""
    n0 = c.count or 0
    a0 = c.api_deltas
    rs = await asyncio.gather(*[bump(c.tok) for _ in range(10)])
    await c.wait(lambda: c.api_deltas >= a0 + 10, 3)
    ok = [r for r in rs if "pid" in r]
    return {"label": label, "sock_pid": c.pid, "bumps_ok": len(ok), "bumps_other_worker": sum(r["pid"] != c.pid for r in ok),
            "api_deltas_received": c.api_deltas - a0, "count_advance_seen": (c.count or 0) - n0, "errors": [r["err"] for r in rs if "err" in r][:2]}


async def redis_restart():
    c = Client(); await c.connect(); await c.emit("incr"); await c.wait(lambda: c.count == 1, 10)
    rcli("SAVE")
    t_down = now(); out = rcli("SHUTDOWN", "SAVE")
    await asyncio.sleep(1.0)
    # an event while redis is down
    await c.emit("incr")
    during = await c.wait(lambda: c.count == 2, 3)
    b_task = asyncio.create_task(bump(c.tok, timeout=60))
    await asyncio.sleep(max(0, a.down - 1 - 3))
    # restart with the same dir so the dump loads
    subprocess.run(["bash", "-c", f". {os.path.dirname(__file__)}/lib.sh; redis_up {a.rport}"], timeout=30)
    t_up = now()
    pending = await c.wait(lambda: (c.count or 0) >= 2, 5)
    br = await b_task
    await asyncio.sleep(2)
    xw = await cross_worker_delivery(c, "after_restart")
    c3 = Client(); err3 = None
    try:
        await c3.connect(); await c3.emit("incr"); w3 = await c3.wait(lambda: c3.count == 1, 20)
    except Exception as e:  # noqa: BLE001
        w3 = None; err3 = repr(e)[:200]
    notify_after = rcli("CONFIG", "GET", "notify-keyspace-events").splitlines()[-1:]
    connected = c.sio.connected
    after_incr = None
    if connected:
        n0 = c.count or 0
        await c.emit("incr"); after_incr = await c.wait(lambda: (c.count or 0) >= n0 + 1, 20)
    xw2 = await cross_worker_delivery(c, "after_new_client")
    st = await get(c.tok)
    for x in (c, c3):
        if x.sio.connected:
            await x.sio.disconnect()
    return {"shutdown": out, "t_down": t_down, "t_up": t_up, "event_during_outage_done_s": during,
            "pending_event_done_after_restart_s": pending, "bump_during_outage": br, "client_still_connected": connected,
            "incr_after_restart_s": after_incr, "new_client_incr_s": w3, "new_client_err": err3,
            "notify_keyspace_after_restart": notify_after, "cross_worker_after_restart": xw, "cross_worker_after_new_client": xw2, "final": st, "client_log_tail": c.log[-6:]}


async def sigstop():
    pidfile = a.redis_pidfile
    rpid = int(open(pidfile).read().strip())
    c = Client(); await c.connect(); await c.emit("incr"); await c.wait(lambda: c.count == 1, 10)
    t_stop = now(); os.kill(rpid, signal.SIGSTOP)
    await asyncio.sleep(1.0)
    await c.emit("incr")
    during = await c.wait(lambda: c.count == 2, a.down - 1)
    b_task = asyncio.create_task(bump(c.tok, timeout=120))
    g_task = asyncio.create_task(get(c.tok, timeout=120))
    await asyncio.sleep(1.0)
    os.kill(rpid, signal.SIGCONT); t_cont = now()
    pending = await c.wait(lambda: (c.count or 0) >= 2, 30)
    br = await b_task; gr = await g_task
    n0 = c.count or 0
    await c.emit("incr"); after = await c.wait(lambda: (c.count or 0) >= n0 + 1, 20)
    st = await get(c.tok)
    await c.sio.disconnect()
    return {"t_stop": t_stop, "t_cont": t_cont, "event_during_stop_done_s": during, "pending_done_after_cont_s": pending,
            "pending_done_at": now() if pending is None else None, "bump": br, "get_during_stop": {k: gr.get(k) for k in ("count", "err")},
            "incr_after_cont_s": after, "final_count": st.get("count"), "expected_count": 4, "client_log_tail": c.log[-6:]}


async def main():
    sc = a.scenario
    if sc.startswith("lost_"):
        r = await lost(sc[5:])
    else:
        r = await globals()[sc]()
    r = {"label": a.label, "scenario": sc, **r}
    print(json.dumps(r))
    if a.out:
        with open(a.out, "a") as f:
            f.write(json.dumps(r) + "\n")

asyncio.run(main())
