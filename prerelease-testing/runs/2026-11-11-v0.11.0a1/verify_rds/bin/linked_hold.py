"""#7738 variant: linked get_state load fails, task stays alive 20 s; time the next foreground event.
Usage: linked_hold.py BASE [mode=fail_hold|fail] [OUT.jsonl] [LABEL]"""
import asyncio, json, sys, time, uuid
import socketio
assert "/envs/vrds-drv/" in sys.executable
base = sys.argv[1].rstrip("/"); mode = sys.argv[2] if len(sys.argv) > 2 else "fail_hold"
out = sys.argv[3] if len(sys.argv) > 3 else None; label = sys.argv[4] if len(sys.argv) > 4 else ""
CNT = "reflex___state____state.lockapp___lockapp____counter"
async def main():
    tok = str(uuid.uuid4()); sio = socketio.AsyncClient(reconnection=False); st = {"count": None}
    @sio.on("event", namespace="/_event")
    async def ev(u):
        d = u.get("delta", {}).get(CNT, {})
        if "count_rx_state_" in d: st["count"] = d["count_rx_state_"]
    await sio.connect(f"{base}?token={tok}", socketio_path="/_event", transports=["websocket"], namespaces=["/_event"], wait_timeout=30)
    em = lambda n, p=None: sio.emit("event", {"name": f"{CNT}.{n}", "payload": p or {}, "router_data": {"pathname": "/", "asPath": "/"}}, namespace="/_event")
    await em("incr")
    while st["count"] != 1: await asyncio.sleep(0.02)
    await em("linked", {"mode": mode, "pause_ms": 0}); await asyncio.sleep(1.0)
    t0 = time.monotonic(); await em("incr")
    while st["count"] != 2 and time.monotonic() - t0 < 40: await asyncio.sleep(0.02)
    r = {"label": label, "mode": mode, "next_event_s": round(time.monotonic() - t0, 3), "count": st["count"]}
    await sio.disconnect(); print(json.dumps(r))
    if out: open(out, "a").write(json.dumps(r) + "\n")
asyncio.run(main())
