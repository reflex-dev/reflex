"""Speak Engine.IO/Socket.IO by hand to send crafted event fields to the backend."""
import asyncio, json, sys, uuid
import websockets

HOST = sys.argv[1]          # e.g. localhost:9587
TOKEN = str(uuid.uuid4())
URL = f"ws://{HOST}/_event/?token={TOKEN}&EIO=4&transport=websocket"


def ev(name, **extra):
    d = {"name": name, "router_data": {"pathname": "/", "asPath": "/"}, "token": TOKEN}
    d.update(extra)
    return d


CASES = [
    ("sampled_parent", ev("reflex___state____state.otelapp___otelapp___s.inc",
        traceparent="00-11111111111111111111111111111111-2222222222222222-01",
        tracestate="vendor=abc")),
    ("unsampled_parent", ev("reflex___state____state.otelapp___otelapp___s.inc",
        traceparent="00-33333333333333333333333333333333-4444444444444444-00")),
    ("hostile_baggage", ev("reflex___state____state.otelapp___otelapp___s.chain",
        traceparent="00-55555555555555555555555555555555-6666666666666666-01",
        baggage="secret=leakme,user=admin")),
    ("garbage_traceparent", ev("reflex___state____state.otelapp___otelapp___s.inc",
        traceparent="i-am-not-a-traceparent")),
    ("nonstring_traceparent", ev("reflex___state____state.otelapp___otelapp___s.inc",
        traceparent=12345, tracestate={"a": 1})),
]


async def main():
    async with websockets.connect(URL, max_size=None) as ws:
        print("open:", (await ws.recv())[:120])
        await ws.send("40/_event,")
        print("ns:", (await ws.recv())[:160])
        await ws.send("42/_event," + json.dumps(["event", ev("reflex___state____state.hydrate")]))
        await asyncio.sleep(1.5)
        for name, payload in CASES:
            await ws.send("42/_event," + json.dumps(["event", payload]))
            print("sent", name)
            await asyncio.sleep(1.0)
        deadline = asyncio.get_event_loop().time() + 4
        while asyncio.get_event_loop().time() < deadline:
            try:
                m = await asyncio.wait_for(ws.recv(), timeout=1)
                print("recv:", m[:160])
            except asyncio.TimeoutError:
                pass
    print("TOKEN", TOKEN)


asyncio.run(main())
