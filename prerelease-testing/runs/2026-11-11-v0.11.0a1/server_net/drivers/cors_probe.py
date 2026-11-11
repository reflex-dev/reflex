"""Raw CORS / origin probe of a Reflex backend.

usage: cors_probe.py <backend_base> <out_json> [origin ...]
For each Origin (and no Origin) probes: GET /ping, GET /_health, OPTIONS /_upload preflight,
POST /_upload (no files), GET /api/greet, OPTIONS /api/greet preflight, polling handshake
GET /_event/?EIO=4&transport=polling, websocket upgrade of /_event/?EIO=4&transport=websocket.
Records status and the access-control-* / vary headers.
"""

import base64
import json
import os
import socket
import sys
from urllib.parse import urlsplit

import httpx

assert "/envs/driver/" in sys.executable, sys.executable

base, out = sys.argv[1].rstrip("/"), sys.argv[2]
origins = sys.argv[3:] or ["http://evil.example"]
NONE = "<none>"


def hdrs(r):
    return {k: v for k, v in r.headers.items() if k.startswith("access-control") or k == "vary"}


def ws_upgrade(origin):
    u = urlsplit(base)
    s = socket.create_connection((u.hostname, u.port), timeout=5)
    key = base64.b64encode(os.urandom(16)).decode()
    lines = [
        f"GET /_event/?EIO=4&transport=websocket HTTP/1.1",
        f"Host: {u.hostname}:{u.port}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {key}",
        "Sec-WebSocket-Version: 13",
    ]
    if origin != NONE:
        lines.append(f"Origin: {origin}")
    s.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
    data = b""
    try:
        while b"\r\n\r\n" not in data:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
        # read the engine.io OPEN packet if upgraded
        if data.startswith(b"HTTP/1.1 101"):
            s.settimeout(2)
            try:
                data += s.recv(4096)
            except socket.timeout:
                pass
    finally:
        s.close()
    head = data.split(b"\r\n")[0].decode(errors="replace")
    body_hint = data.split(b"\r\n\r\n", 1)[1][:60] if b"\r\n\r\n" in data else b""
    return {"status_line": head, "after": body_hint.decode(errors="replace")}


res = {}
with httpx.Client(timeout=5, trust_env=False) as c:
    for origin in [NONE, *origins]:
        h = {} if origin == NONE else {"Origin": origin}
        pre = {**h, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type,reflex-client-token,reflex-event-handler"}
        r = {}

        def rec(name, resp):
            r[name] = {"status": resp.status_code, **hdrs(resp)}

        for name, fn in [
            ("GET /ping", lambda: c.get(base + "/ping", headers=h)),
            ("GET /_health", lambda: c.get(base + "/_health", headers=h)),
            ("OPTIONS /_upload", lambda: c.options(base + "/_upload", headers=pre)),
            ("POST /_upload", lambda: c.post(base + "/_upload", headers=h, files={"files": ("a.txt", b"x")})),
            ("GET /api/greet", lambda: c.get(base + "/api/greet", headers=h)),
            ("OPTIONS /api/greet", lambda: c.options(base + "/api/greet", headers={**h, "Access-Control-Request-Method": "GET"})),
            ("GET poll", lambda: c.get(base + "/_event/?EIO=4&transport=polling", headers=h)),
        ]:
            try:
                rec(name, fn())
            except Exception as e:  # noqa: BLE001
                r[name] = {"error": repr(e)[:200]}
        try:
            r["WS upgrade"] = ws_upgrade(origin)
        except Exception as e:  # noqa: BLE001
            r["WS upgrade"] = {"error": repr(e)[:200]}
        res[origin] = r

with open(out, "w") as f:
    json.dump(res, f, indent=1)

# compact table
names = list(next(iter(res.values())).keys())
for origin, r in res.items():
    cells = []
    for n in names:
        v = r[n]
        if "error" in v:
            cells.append(f"{n}=ERR")
            continue
        if n == "WS upgrade":
            cells.append(f"WS={v['status_line'].split(' ')[1] if ' ' in v['status_line'] else v['status_line']}")
            continue
        acao = v.get("access-control-allow-origin", "-")
        acac = "C" if v.get("access-control-allow-credentials") else ""
        cells.append(f"{n.split()[1]}:{v['status']}/{acao}{('+' + acac) if acac else ''}")
    print(f"{origin:28s} " + " ".join(cells))
