"""Item 8: dispatch a worker-side event over reflex socket.io to force worker logging."""
import asyncio, sys, uuid, socketio

BACKEND = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8140"
HANDLER = sys.argv[2] if len(sys.argv) > 2 else "reflex___state____state.pep695app___pep695app____alias_state.do_log"

async def main():
    token = str(uuid.uuid4())
    c = socketio.AsyncClient(reconnection=False)
    got = []
    @c.on("event", namespace="/_event")
    async def _on_event(data):
        got.append(data)
    # connect with token in query so backend links sid->token
    url = f"{BACKEND}?token={token}"
    await c.connect(url, socketio_path="_event", namespaces=["/_event"], transports=["websocket"], wait_timeout=10)
    await asyncio.sleep(0.4)
    router_data = {"pathname": "/", "query": {}, "token": token}
    # hydrate first to initialize state
    for name in ["reflex___state____state.hydrate", HANDLER, HANDLER, HANDLER]:
        await c.emit("event", {"token": token, "name": name, "payload": {}, "router_data": router_data}, namespace="/_event")
        await asyncio.sleep(0.4)
    await asyncio.sleep(0.8)
    print(f"dispatched; connected={c.connected}; events_received={len(got)}")
    await c.disconnect()

asyncio.run(main())
