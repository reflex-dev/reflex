"""ES-1 over the socket, on both versions, with a second (bystander) client.

Usage: NO_PROXY=... $SB/envs/events_state-sio/bin/python probe_sio_verify.py http://localhost:<BP> [state_schema]
Client A sends: a valid envelope, malformed envelopes (dict handler), generic garbage to a dataclass-annotated
handler (the pre-existing "client sent garbage" path), then a plain dict. Client B (connected the whole time) sends a
plain event after A's bad messages. Prints what each client received; read the server log for tracebacks.
"""

import json
import sys
import time
import uuid

import socketio

base = sys.argv[1]
schema = sys.argv[2] if len(sys.argv) > 2 else None
STORE = "reflex___state____state.formsapp___formsapp____state.store"
STORE_DC = "reflex___state____state.formsapp___formsapp____state.store_dc"


class Client:
    def __init__(self, label):
        self.label = label
        self.token = str(uuid.uuid4())
        self.events = []
        self.sio = socketio.Client(logger=False, engineio_logger=False)
        self.sio.on("*", namespace="/_event")(lambda event, *args: self.events.append((event, json.dumps(args)[:400])))
        self.sio.on("disconnect", namespace="/_event")(lambda *a: self.events.append(("disconnect", str(a))))
        boot = {"name": "reflex___state____state.hydrate_and_load", "payload": {"hashes": []}, "router_data": {"pathname": "/verify", "asPath": "/verify"}, "token": self.token}
        auth = {"event": boot}
        if schema:
            auth["state_schema"] = schema
        self.sio.connect(base + "?token=" + self.token, namespaces=["/_event"], transports=["websocket"], socketio_path="/_event", auth=auth, wait_timeout=10)

    def send(self, name, payload, label):
        before = len(self.events)
        ev = {"token": self.token, "name": name, "payload": payload, "router_data": {"pathname": "/verify", "asPath": "/verify"}}
        self.sio.emit("event", json.dumps(ev), namespace="/_event")
        time.sleep(1.2)
        got = self.events[before:]
        kinds = []
        for k, v in got:
            if "_call_function" in v and "toast" in v:
                m = v.find("description")
                kinds.append("TOAST " + v[m + 14 : m + 110].replace("\\\\n", " ").replace("\\n", " "))
            elif '"delta"' in v:
                m = v.find("results_json")
                kinds.append("DELTA " + (v[m : m + 120] if m >= 0 else v[:120]))
            else:
                kinds.append(f"{k} {v[:120]}")
        print(f"--- [{self.label}] {label}\n    payload={json.dumps(payload)[:140]}\n    received {len(got)}: " + " | ".join(kinds) + f"\n    connected={self.sio.connected}")


a = Client("A")
b = Client("B")
time.sleep(1.5)
print("A after connect:", [k for k, _ in a.events], "B after connect:", [k for k, _ in b.events])
a.send(STORE, {"form": "ok_env", "form_data": {"__reflex_form_data__": [["a", "1"], ["a", "2"]]}}, "valid envelope -> dict handler")
a.send(STORE, {"form": "bad_str", "form_data": {"__reflex_form_data__": "not-a-list"}}, "envelope value is a string")
a.send(STORE, {"form": "bad_pairs", "form_data": {"__reflex_form_data__": [["only-one"]]}}, "envelope pairs of length 1")
a.send(STORE, {"form": "bad_unhashable", "form_data": {"__reflex_form_data__": [[["x"], "v"]]}}, "envelope key unhashable")
b.send(STORE, {"form": "bystander", "form_data": {"b": "fine"}}, "bystander B sends a plain dict right after A's bad ones")
a.send(STORE_DC, {"form": "garbage_int", "form_data": 5}, "generic garbage: int to a dataclass-annotated handler")
a.send(STORE_DC, {"form": "garbage_dict", "form_data": {"zzz": 1}}, "generic garbage: wrong keys to a dataclass-annotated handler")
a.send(STORE, {"form": "after", "form_data": {"a": "still-works"}}, "plain dict after the bad ones")
a.sio.disconnect()
b.sio.disconnect()
print("done; A events", len(a.events), "B events", len(b.events))
