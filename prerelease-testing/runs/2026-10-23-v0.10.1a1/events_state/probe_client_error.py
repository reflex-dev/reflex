"""EVT-02: emit the socket.io-level `client_error` event with no / odd payloads; the server must not traceback.

Usage: NO_PROXY=... $SB/envs/events_state-sio/bin/python probe_client_error.py http://localhost:<BP> [state_schema]
"""

import sys
import time
import uuid

import socketio

base = sys.argv[1]
schema = sys.argv[2] if len(sys.argv) > 2 else None
token = str(uuid.uuid4())
events = []
sio = socketio.Client(logger=False, engineio_logger=False)


@sio.on("*", namespace="/_event")
def catch_all(event, *args):
    events.append((event, [str(x)[:120] for x in args]))


boot = {"name": "reflex___state____state.hydrate_and_load", "payload": {"hashes": []}, "router_data": {"pathname": "/", "asPath": "/"}, "token": token}
auth = {"event": boot}
if schema:
    auth["state_schema"] = schema
sio.connect(base + "?token=" + token, namespaces=["/_event"], transports=["websocket"], socketio_path="/_event", auth=auth, wait_timeout=10)
time.sleep(1)
for label, args in [
    ("no payload at all", ()),
    ("empty dict", ({},)),
    ("None", (None,)),
    ("string", ("boom",)),
    ("list", ([1, 2],)),
    ("dict without expected keys", ({"foo": "bar"},)),
    ("dict with huge stack", ({"error": "x", "stack": "y" * 100000},)),
    ("two positional args", ({"a": 1}, {"b": 2})),
]:
    before = len(events)
    sio.emit("client_error", *args, namespace="/_event")
    time.sleep(0.8)
    print(f"{label:28} connected={sio.connected} received={events[before:]}")
sio.emit("event", {"token": token, "name": "reflex___state____state.formsapp___formsapp____state.store", "payload": {"form": "after_ce", "form_data": {"a": "ok"}}, "router_data": {"pathname": "/", "asPath": "/"}}, namespace="/_event")
time.sleep(1.5)
print("normal event after client_error ->", [e for e in events if e[0] == "event"][-1:] and "delta received" or "NO DELTA")
sio.disconnect()
