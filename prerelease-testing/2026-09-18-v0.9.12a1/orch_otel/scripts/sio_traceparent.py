"""Send crafted events (traceparent/tracestate/baggage) straight over socket.io."""
import json, sys, time, uuid
import socketio

BASE = sys.argv[1]
token = str(uuid.uuid4())
sio = socketio.Client()
got = []
sio.on("event", lambda d: got.append(d), namespace="/_event")


@sio.event(namespace="/_event")
def connect():
    print("connected")


sio.connect(f"{BASE}?token={token}", socketio_path="/_event",
            namespaces=["/_event"], transports=["polling"], wait_timeout=15)

def ev(name, **extra):
    d = {"name": name, "router_data": {"pathname": "/", "asPath": "/"}, "token": token}
    d.update(extra)
    return d

CASES = [
    ("sampled_parent", ev("reflex___state____state.otelapp___otelapp___s.inc",
        traceparent="00-11111111111111111111111111111111-2222222222222222-01",
        tracestate="vendor=abc")),
    ("unsampled_parent", ev("reflex___state____state.otelapp___otelapp___s.inc",
        traceparent="00-33333333333333333333333333333333-4444444444444444-00")),
    ("hostile_baggage", ev("reflex___state____state.otelapp___otelapp___s.inc",
        traceparent="00-55555555555555555555555555555555-6666666666666666-01",
        baggage="secret=leakme,user=admin")),
    ("garbage_traceparent", ev("reflex___state____state.otelapp___otelapp___s.inc",
        traceparent="i-am-not-a-traceparent")),
    ("nonstring_traceparent", ev("reflex___state____state.otelapp___otelapp___s.inc",
        traceparent=12345, tracestate={"a": 1})),
]

sio.emit("event", ev("reflex___state____state.hydrate"), namespace="/_event")
time.sleep(1.5)
for name, payload in CASES:
    print("sending", name)
    sio.emit("event", payload, namespace="/_event")
    time.sleep(1.0)
time.sleep(3)
print("deltas received:", len(got))
sio.disconnect()
print("token:", token)
