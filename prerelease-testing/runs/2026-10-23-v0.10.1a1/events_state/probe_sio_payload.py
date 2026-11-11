"""Send crafted event payloads to a running formsapp backend over socket.io and report what comes back.

Usage: NO_PROXY=... $SB/envs/events_state-sio/bin/python probe_sio_payload.py http://localhost:<BP> [state_schema]
Cases: a malformed `__reflex_form_data__` envelope in a dict-annotated arg (the backend's decoder calls
dict(entries) on it), the same for an unannotated arg, a valid envelope, and `client_error` with no payload (EVT-02).
Watch the server log while this runs.
"""

import json
import sys
import time
import uuid

import socketio

base = sys.argv[1]
schema = sys.argv[2] if len(sys.argv) > 2 else None
token = str(uuid.uuid4())
HANDLER = "reflex___state____state.formsapp___formsapp____state.store"
HANDLER_ANY = "reflex___state____state.formsapp___formsapp____state.store_any"

events = []
sio = socketio.Client(logger=False, engineio_logger=False)


@sio.on("event", namespace="/_event")
def on_event(data):
    events.append(("event", data if isinstance(data, str) else json.dumps(data)))


@sio.on("state_mismatch", namespace="/_event")
def on_mismatch(data=None):
    events.append(("state_mismatch", data))


@sio.on("disconnect", namespace="/_event")
def on_disconnect(*a):
    events.append(("disconnect", a))


@sio.on("*", namespace="/_event")
def catch_all(event, *args):
    events.append((event, [str(x)[:200] for x in args]))


# The frontend passes the token as a query parameter and rides the hydrate event in the CONNECT auth
# (state.js `bootAuth`): {"event": <hydrate_and_load event>, "state_schema": <hash>}.
boot = {"name": "reflex___state____state.hydrate_and_load", "payload": {"hashes": []}, "router_data": {"pathname": "/legacy", "asPath": "/legacy"}, "token": token}
auth = {"event": boot}
if schema:
    auth["state_schema"] = schema
sio.connect(base + "?token=" + token, namespaces=["/_event"], transports=["websocket"], socketio_path="/_event", auth=auth, wait_timeout=10)
time.sleep(1.5)
print("after connect: events", [(k, str(v)[:120]) for k, v in events])


def send(name, payload, label):
    before = len(events)
    ev = {"token": token, "name": name, "payload": payload, "router_data": {"pathname": "/legacy", "asPath": "/legacy"}}
    sio.emit("event", json.dumps(ev), namespace="/_event")
    time.sleep(1.5)
    got = events[before:]
    print(f"--- {label}\n    sent payload={json.dumps(payload)[:160]}\n    received {len(got)}: " + "; ".join(f"{k}: {str(v)[:260]}" for k, v in got))
    print("    connected:", sio.connected)


send(HANDLER, {"form": "ok_env", "form_data": {"__reflex_form_data__": [["a", "1"], ["a", "2"]]}}, "valid envelope -> dict handler")
send(HANDLER, {"form": "bad_str", "form_data": {"__reflex_form_data__": "not-a-list"}}, "envelope value is a string")
send(HANDLER, {"form": "bad_int", "form_data": {"__reflex_form_data__": 5}}, "envelope value is an int")
send(HANDLER, {"form": "bad_pairs", "form_data": {"__reflex_form_data__": [["only-one"]]}}, "envelope pairs of length 1")
send(HANDLER, {"form": "bad_triple", "form_data": {"__reflex_form_data__": [[1, 2, 3]]}}, "envelope pairs of length 3")
send(HANDLER, {"form": "bad_unhashable", "form_data": {"__reflex_form_data__": [[["x"], "v"]]}}, "envelope key unhashable")
send(HANDLER_ANY, {"form": "any_bad", "form_data": {"__reflex_form_data__": "zzz"}}, "unannotated handler, bad envelope")
send(HANDLER, {"form": "after", "form_data": {"a": "still-works"}}, "plain dict after the bad ones")
send(HANDLER, {"form": "nested", "form_data": {"x": {"__reflex_form_data__": "zzz"}}}, "envelope nested one level down (should be untouched)")
send("reflex___state____state.client_error", {}, "EVT-02: client_error with no payload")
send("reflex___state____state.client_error", {"stack": "x"}, "client_error with a payload")
send(HANDLER, {"form": "after2", "form_data": {"a": "still-works-2"}}, "plain dict after client_error")
sio.disconnect()
print("done; events seen:", len(events))
