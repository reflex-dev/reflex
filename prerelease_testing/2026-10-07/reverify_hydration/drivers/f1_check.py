"""F1 verifier driver: load a page in a fresh (or restored) context, capture /_event websocket frames,
decode which states/vars each inbound delta carries (and whether the root carries is_hydrated_rx_state_),
and dump localStorage / sessionStorage / cookies (with expiry).

Usage: f1_check.py URL STATE_IN|- STATE_OUT|- OUT_JSON [ids,comma,separated]
"""
import json
import sys
import time

from playwright.sync_api import sync_playwright

assert "/envs/driver/" in sys.executable, sys.executable
CHROMIUM = "/opt/pw-browsers/chromium"
url, state_in, state_out, out_json = sys.argv[1:5]
ids = sys.argv[5].split(",") if len(sys.argv) > 5 else ["theme", "consent", "vid"]
ROOT = "reflex___state____state"


def decode(p):
    if not isinstance(p, str):
        return None
    if len(p) > 2 and p[0] == "4" and p[2:3] == "/":
        comma = p.find(",", 2)
        p = p[:2] + (p[comma + 1:] if comma != -1 else "")
    if p.startswith("42"):
        try:
            return ("event", json.loads(p[2:]))
        except Exception:
            return ("event-trunc", p[:300])
    if p.startswith("40"):
        try:
            return ("connect", json.loads(p[2:]) if len(p) > 2 else None)
        except Exception:
            return ("connect-trunc", p[:300])
    return ("other", p[:40])


frames = []
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROMIUM)
    ctx = b.new_context(storage_state=state_in) if state_in != "-" else b.new_context()
    page = ctx.new_page()
    t0 = time.time()

    def on_ws(ws):
        if "_event" not in ws.url:
            return
        ws.on("framesent", lambda p: frames.append(("out", round(time.time() - t0, 3), p)))
        ws.on("framereceived", lambda p: frames.append(("in", round(time.time() - t0, 3), p)))

    page.on("websocket", on_ws)
    console = []
    page.on("console", lambda m: console.append(f"{m.type}: {m.text[:300]}"))
    page.goto(url)
    hyd = False
    for _ in range(300):
        try:
            if page.locator("#hyd-flag").inner_text(timeout=200) == "H:yes":
                hyd = True
                break
        except Exception:
            pass
        page.wait_for_timeout(100)
    page.wait_for_timeout(1000)
    shown = {}
    for i in ids:
        try:
            shown[i] = page.locator(f"#{i}").first.inner_text(timeout=500)
        except Exception:
            shown[i] = None
    storage = page.evaluate("""() => ({
        local: Object.fromEntries(Object.keys(localStorage).map(k => [k, localStorage.getItem(k)])),
        session: Object.fromEntries(Object.keys(sessionStorage).filter(k => k !== 'token').map(k => [k, sessionStorage.getItem(k)])),
    })""")
    cookies = [{"name": c["name"], "value": c["value"], "expires": c["expires"]} for c in ctx.cookies()]
    if state_out != "-":
        ctx.storage_state(path=state_out)
    b.close()

decoded = []
for d, t, p in frames:
    k = decode(p)
    if k is None:
        continue
    kind, payload = k
    item = {"dir": d, "t": t, "kind": kind, "len": len(p)}
    if kind == "connect" and isinstance(payload, dict):
        ev = payload.get("event") or {}
        pl = ev.get("payload") or {}
        item["boot"] = ev.get("name")
        item["boot_router_data"] = ev.get("router_data")
        item["boot_vars"] = pl.get("vars")
        item["n_hashes"] = len(pl.get("hashes") or [])
    elif kind == "event" and isinstance(payload, list) and len(payload) > 1 and isinstance(payload[1], dict):
        upd = payload[1]
        if "delta" in upd:
            delta = upd.get("delta") or {}
            item["delta"] = {s: v for s, v in delta.items()}
            item["root_has_is_hydrated"] = ("is_hydrated_rx_state_" in delta.get(ROOT, {})) if ROOT in delta else "root-absent"
            item["root_is_hydrated"] = delta.get(ROOT, {}).get("is_hydrated_rx_state_")
        elif "name" in upd:
            item["name"] = upd["name"]
            item["router_data"] = upd.get("router_data")
            item["payload"] = upd.get("payload")
    elif kind == "event" and isinstance(payload, list):
        item["sio_event"] = payload
    decoded.append(item)

res = {"url": url, "hydrated": hyd, "shown": shown, "localStorage": storage["local"],
       "sessionStorage": storage["session"], "cookies": cookies, "frames": decoded,
       "console_err_warn": [c for c in console if c.startswith(("error", "warning"))]}
with open(out_json, "w") as f:
    json.dump(res, f, indent=1, default=str)
# compact stdout summary
print(json.dumps({"hydrated": hyd, "shown": shown, "localStorage": storage["local"],
                  "sessionStorage": storage["session"], "cookies": [(c["name"], c["value"]) for c in cookies]}))
for it in decoded:
    if it["kind"] == "connect":
        print(f"  {it['dir'].upper()} CONNECT boot=", it.get("boot"), "router=", it.get("boot_router_data"), "vars=", it.get("boot_vars"), "n_hashes=", it.get("n_hashes"))
    elif "delta" in it:
        summ = {s.split(".")[-1]: (sorted(v.keys()) if isinstance(v, dict) else v) for s, v in it["delta"].items()}
        print(f"  {it['dir'].upper()} t={it['t']} delta root_has_is_hydrated={it['root_has_is_hydrated']} root_is_hydrated={it['root_is_hydrated']} states={json.dumps(summ)}")
    elif "name" in it:
        print(f"  {it['dir'].upper()} t={it['t']} event {it['name'].split('.')[-1]} router={it.get('router_data')}")
