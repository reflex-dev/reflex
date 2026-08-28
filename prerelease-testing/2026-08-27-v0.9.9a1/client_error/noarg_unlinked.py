import asyncio, socketio, sys
async def main():
    c = socketio.AsyncClient(reconnection=False)
    # connect WITHOUT a token -> sid is not linked (unknown sid)
    await c.connect("http://localhost:8220", socketio_path="_event", namespaces=["/_event"], transports=["websocket"], wait_timeout=10)
    await asyncio.sleep(0.3)
    for _ in range(5):
        await c.emit("client_error", namespace="/_event")  # no data arg
    await asyncio.sleep(0.5)
    print("UNLINKED_NOARG sent 5 (connected=%s)" % c.connected)
    await c.disconnect()
asyncio.run(main())
