"""Item 2 (FINDING-004): client_error no-arg emit must NOT raise a TypeError traceback;
a normal dict payload still processes."""
import asyncio, sys, uuid, socketio

BACKEND = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8140"

async def main():
    # (1) no-token (unknown sid) no-arg emit x5
    c = socketio.AsyncClient(reconnection=False)
    await c.connect(BACKEND, socketio_path="_event", namespaces=["/_event"], transports=["websocket"], wait_timeout=10)
    await asyncio.sleep(0.3)
    for _ in range(5):
        await c.emit("client_error", namespace="/_event")   # NO payload
    await asyncio.sleep(0.5)
    print(f"[noarg] sent 5 no-arg emits (connected={c.connected})")
    # (2) a normal dict payload (still unknown sid, but valid shape) x3
    for _ in range(3):
        await c.emit("client_error", {"message": "hello from probe", "stack": "x"}, namespace="/_event")
    await asyncio.sleep(0.5)
    print(f"[dict] sent 3 dict-payload emits (connected={c.connected})")
    await c.disconnect()
    # (3) token-linked emit so it reaches the report path
    token = str(uuid.uuid4())
    c2 = socketio.AsyncClient(reconnection=False)
    await c2.connect(f"{BACKEND}?token={token}", socketio_path="_event", namespaces=["/_event"], transports=["websocket"], wait_timeout=10)
    await asyncio.sleep(0.3)
    await c2.emit("client_error", {"message": "linked probe report"}, namespace="/_event")
    await asyncio.sleep(0.5)
    print(f"[linked] sent 1 dict emit as linked sid (connected={c2.connected})")
    await c2.disconnect()

asyncio.run(main())
