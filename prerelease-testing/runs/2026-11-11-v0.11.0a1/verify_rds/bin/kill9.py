"""kill -9 the worker serving a token mid-event; measure recovery.
Usage: kill9.py BASE REDIS_PORT OUT.jsonl LABEL kill TOKFILE   (kills; granian then stops the whole server)
       kill9.py BASE REDIS_PORT OUT.jsonl LABEL resume TOKFILE (after the server was restarted: reconnect same token, time first event)"""
import asyncio, json, os, signal, subprocess, sys, time, uuid
import aiohttp, socketio
assert "/envs/vrds-drv/" in sys.executable
base, rport = sys.argv[1].rstrip("/"), sys.argv[2]
out, label, mode, tokfile = sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]
CNT = "reflex___state____state.lockapp___lockapp____counter"
T0 = time.monotonic(); now = lambda: round(time.monotonic() - T0, 3)
log = []

def mk(tok):
    sio = socketio.AsyncClient(reconnection=False)
    st = {"count": None, "pid": None}
    @sio.on("event", namespace="/_event")
    async def ev(u):
        d = u.get("delta", {}).get(CNT, {})
        if "count_rx_state_" in d: st["count"] = d["count_rx_state_"]
        if "last_pid_rx_state_" in d: st["pid"] = int(d["last_pid_rx_state_"])
        log.append((now(), "event", json.dumps(u)[:160]))
    @sio.on("new_token", namespace="/_event")
    async def nt(t): log.append((now(), "new_token", t))
    @sio.on("connect", namespace="/_event")
    async def c(): log.append((now(), "ns connect"))
    @sio.on("connect_error", namespace="/_event")
    async def ce(d): log.append((now(), "ns connect_error", str(d)[:200]))
    @sio.on("disconnect", namespace="/_event")
    async def dc(*a): log.append((now(), "ns disconnect", str(a)))
    return sio, st

async def emit(sio, name, payload=None):
    await sio.emit("event", {"name": f"{CNT}.{name}", "payload": payload or {}, "router_data": {"pathname": "/", "asPath": "/"}}, namespace="/_event")

async def until(pred, t):
    t0 = time.monotonic()
    while time.monotonic() - t0 < t:
        if pred(): return round(time.monotonic() - t0, 3)
        await asyncio.sleep(0.02)
    return None

async def main():
    if mode == "connect_only":
        # Connect, do one incr, stay connected until the server goes away (clean-stop control).
        tok = str(uuid.uuid4()); open(tokfile, "w").write(tok); open(tokfile + ".t", "w").write(str(time.time()))
        s1, st1 = mk(tok)
        await s1.connect(f"{base}?token={tok}", socketio_path="/_event", transports=["websocket"], namespaces=["/_event"], wait_timeout=30)
        await emit(s1, "incr"); await until(lambda: st1["count"] == 1, 10)
        await until(lambda: not s1.connected, 20)
        res = {"label": label, "mode": mode, "count": st1["count"], "pid": st1["pid"]}
    elif mode == "kill":
        tok = str(uuid.uuid4()); open(tokfile, "w").write(tok)
        s1, st1 = mk(tok)
        await s1.connect(f"{base}?token={tok}", socketio_path="/_event", transports=["websocket"], namespaces=["/_event"], wait_timeout=30)
        await emit(s1, "incr"); await until(lambda: st1["count"] == 1, 10)
        pid = st1["pid"]
        await emit(s1, "slow", {"ms": 5000}); await asyncio.sleep(0.5)
        os.kill(pid, signal.SIGKILL); t_kill = time.time()
        pttl = subprocess.run(["redis-cli", "-p", rport, "PTTL", f"{tok}_lock"], capture_output=True, text=True).stdout.strip()
        open(tokfile + ".t", "w").write(str(t_kill))
        res = {"label": label, "mode": mode, "killed_pid": pid, "lock_pttl_ms_at_kill": pttl}
    else:
        tok = open(tokfile).read().strip(); t_kill = float(open(tokfile + ".t").read())
        pttl = subprocess.run(["redis-cli", "-p", rport, "PTTL", f"{tok}_lock"], capture_output=True, text=True).stdout.strip()
        t_resume = time.time()
        s2, st2 = mk(tok)
        t0 = time.monotonic()
        await s2.connect(f"{base}?token={tok}", socketio_path="/_event", transports=["websocket"], namespaces=["/_event"], wait_timeout=30)
        conn_s = round(time.monotonic() - t0, 3)
        t1 = time.monotonic(); await emit(s2, "incr")
        w = await until(lambda: st2["count"] is not None, 40)
        res = {"label": label, "mode": mode, "since_kill_at_resume_s": round(t_resume - t_kill, 2), "lock_pttl_ms_at_resume": pttl,
               "connect_s": conn_s, "first_incr_s": w, "count": st2["count"], "first_event_done_since_kill_s": round(time.time() - t_kill, 2), "log": log[-6:]}
        await s2.disconnect()
    print(json.dumps(res))
    open(out, "a").write(json.dumps(res) + "\n")

asyncio.run(main())
