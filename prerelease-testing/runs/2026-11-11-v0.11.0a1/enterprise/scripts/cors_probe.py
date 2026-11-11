"""CORS probe of a prod reflex-enterprise backend (#7641): raw Origin/preflight checks + real cross-origin browser fetches.

Usage: cors_probe.py <backend_url e.g. http://localhost:8380> <label> [foreign_port=3399]
- httpx: for each endpoint, a preflight OPTIONS and the real request with Origin: http://localhost:<foreign_port>
  -> status + access-control-allow-origin / -credentials.
- Chromium: a page served from http://localhost:<foreign_port>/ (our own http.server) does fetch() to the backend;
  the same fetches from a page on the backend origin itself (same-origin control). Also a socket.io polling handshake.
Writes $SB/apps/enterprise/out/cors_<label>.json and prints a table.
"""

import http.server
import json
import sys
import threading
from pathlib import Path

import httpx
import playwright
from playwright.sync_api import sync_playwright

assert "/envs/driver/" in playwright.__file__, playwright.__file__
BE, LABEL = sys.argv[1], sys.argv[2]
FP = int(sys.argv[3]) if len(sys.argv) > 3 else 3399
FOREIGN = f"http://localhost:{FP}"
E = Path("/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/enterprise")
out = {"label": LABEL, "raw": {}, "browser": {}}
c = httpx.Client(base_url=BE, timeout=20, trust_env=False)
tok = c.post("/_reflex/auth/token").json().get("access_token")
EP = [
    ("GET", "/ping", None, {}),
    ("POST", "/_reflex/auth/token", None, {}),
    ("POST", "/_reflex/event/xcut___xcut____pub/probe", {"via": "cors"}, {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}),
    ("POST", "/_reflex/retrieve_state", None, {"Authorization": f"Bearer {tok}"}),
    ("POST", "/_reflex/mcp/", {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "cors-probe", "version": "0"}}},
     {"Authorization": f"Bearer {tok}", "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}),
    ("GET", "/.well-known/oauth-authorization-server", None, {}),
    ("POST", "/_reflex/cookies/sync", {}, {"Content-Type": "application/json"}),
    ("GET", "/_event/?EIO=4&transport=polling", None, {}),
]
print(f"{'endpoint':55s} {'preflight':>10s} {'ACAO(pre)':>24s} {'status':>6s} {'ACAO':>24s} ACAC")
for m, path, body, hdrs in EP:
    pre = c.options(path, headers={"Origin": FOREIGN, "Access-Control-Request-Method": m,
                                   "Access-Control-Request-Headers": ",".join(k.lower() for k in hdrs) or "content-type"})
    r = c.request(m, path, headers={"Origin": FOREIGN, **hdrs}, json=body) if body is not None else c.request(m, path, headers={"Origin": FOREIGN, **hdrs})
    rec = {"preflight": pre.status_code, "pre_acao": pre.headers.get("access-control-allow-origin"),
           "status": r.status_code, "acao": r.headers.get("access-control-allow-origin"),
           "acac": r.headers.get("access-control-allow-credentials"), "body": r.text[:160]}
    out["raw"][f"{m} {path}"] = rec
    print(f"{m + ' ' + path[:50]:55s} {rec['preflight']:>10} {str(rec['pre_acao']):>24s} {rec['status']:>6} {str(rec['acao']):>24s} {rec['acac']}")


class H(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        b = b"<!doctype html><title>foreign</title><p id=x>foreign origin page</p>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):
        pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", FP), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
JS = """async ([be, tok]) => {
  const res = {};
  const go = async (name, url, init) => {
    try { const r = await fetch(url, init); const t = await r.text(); res[name] = r.status + ' ' + t.slice(0, 80); }
    catch (e) { res[name] = 'BLOCKED ' + e.message; }
  };
  await go('ping', be + '/ping', {});
  await go('token', be + '/_reflex/auth/token', {method: 'POST'});
  await go('event', be + '/_reflex/event/xcut___xcut____pub/probe', {method: 'POST', headers: {'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'}, body: '{"via":"browser"}'});
  await go('mcp', be + '/_reflex/mcp/', {method: 'POST', headers: {'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}, body: JSON.stringify({jsonrpc: '2.0', id: 1, method: 'initialize', params: {protocolVersion: '2025-06-18', capabilities: {}, clientInfo: {name: 'b', version: '0'}}})});
  await go('cookie_sync', be + '/_reflex/cookies/sync', {method: 'POST', credentials: 'include', headers: {'Content-Type': 'application/json'}, body: '{}'});
  await go('socketio_poll', be + '/_event/?EIO=4&transport=polling', {});
  return res;
}"""
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for where, url in (("cross_origin", FOREIGN + "/"), ("same_origin", BE + "/ping")):
        pg = b.new_page()
        pg.goto(url)
        out["browser"][where] = pg.evaluate(JS, [BE, tok])
        print(where, json.dumps(out["browser"][where])[:900])
        pg.close()
    b.close()
srv.shutdown()
(E / "out").mkdir(exist_ok=True)
(E / "out" / f"cors_{LABEL}.json").write_text(json.dumps(out, indent=1))
