"""Minimal raw socket.io probe: connect to /_event, send one event, dump everything received to a JSON file.

usage: socket_probe.py <backend_url> <handler_full_name> <seconds> <out.json>
"""
import asyncio, json, sys, time, uuid
import socketio
url, name, secs, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
NS = "/_event"
async def main():
    token = str(uuid.uuid4())
    sio = socketio.AsyncClient(reconnection=False)
    got = []
    @sio.on("*", namespace=NS)
    async def any_event(event, *args):
        got.append({"t": round(time.perf_counter()-t0,3), "event": event, "args": args})
    @sio.event(namespace=NS)
    async def disconnect(*a):
        got.append({"disconnect": a})
    t0 = time.perf_counter()
    await sio.connect(f"{url}?token={token}", socketio_path="/_event", namespaces=[NS], transports=["websocket"], wait_timeout=20)
    ev = {"token": token, "name": name, "payload": {}, "router_data": {"pathname": "/", "asPath": "/", "query": {}}}
    await sio.emit("event", ev, namespace=NS)
    await asyncio.sleep(secs)
    await sio.emit("ping", namespace=NS)
    await asyncio.sleep(0.5)
    json.dump(got, open(out, "w"), indent=1, default=str)
    for g in got:
        if "args" in g and g["args"] and isinstance(g["args"][0], dict) and "delta" in g["args"][0]:
            for k, v in g["args"][0]["delta"].items():
                print(f"  t={g['t']} delta[{k}] keys={list(v)}")
            print("   other:", {k: v for k, v in g["args"][0].items() if k != "delta"})
        else:
            print(" ", g)
    await sio.disconnect()
asyncio.run(main())
