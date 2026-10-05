"""Force a websocket reconnect and record which router vars come back."""
import json, sys
from playwright.sync_api import sync_playwright
BASE, OUT = sys.argv[1], sys.argv[2]
frames, console, errs = [], [], []
LAB = {"l": "boot"}

def hook(ws):
    ws.on("framereceived", lambda x: frames.append((LAB["l"], "recv", x if isinstance(x, str) else repr(x))))
    ws.on("framesent", lambda x: frames.append((LAB["l"], "sent", x if isinstance(x, str) else repr(x))))

def report(label, start):
    print(f"\n### {label}")
    for lab, d, pl in frames[start:]:
        i = pl.find("[")
        if i < 0:
            print(f"  {d}: {pl[:120]}")
            continue
        try:
            obj = json.loads(pl[i:])
        except Exception:
            print(f"  {d}: <undecodable {len(pl)}B> {pl[:120]}")
            continue
        if obj[0] != "event":
            continue
        body = obj[1]
        if d == "sent":
            print(f"  -> {body.get('name')} rd={json.dumps(body.get('router_data'))[:100]}")
        else:
            delta = body.get("delta", {})
            root = delta.get("reflex___state____state", {})
            rk = sorted(k.replace("_rx_state_", "") for k in root if k.startswith("rx_router_"))
            print(f"  <- {len(pl)}B ROUTER={rk} states={ {k.split('.')[-1]: sorted(x.replace('_rx_state_','') for x in v) for k,v in delta.items() if v} }")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    pg = ctx.new_page()
    pg.on("console", lambda m: console.append((LAB["l"], m.type, m.text[:300])))
    pg.on("pageerror", lambda e: errs.append((LAB["l"], str(e)[:300])))
    pg.on("websocket", hook)
    LAB["l"] = "load"
    pg.goto(BASE + "/items/42", wait_until="networkidle"); pg.wait_for_timeout(2500)
    s = len(frames); LAB["l"] = "bump_before"
    pg.click("#btn_bump"); pg.wait_for_timeout(1200); report("bump before disconnect", s)
    s = len(frames); LAB["l"] = "offline"
    ctx.set_offline(True); pg.wait_for_timeout(4000)
    LAB["l"] = "online"
    ctx.set_offline(False); pg.wait_for_timeout(8000)
    report("reconnect (offline->online)", s)
    print("  counter:", pg.query_selector("#counter").inner_text())
    print("  cv_session:", pg.query_selector("#cv_session").inner_text())
    print("  cv_auto_path:", pg.query_selector("#cv_auto_path").inner_text())
    s = len(frames); LAB["l"] = "bump_after"
    pg.click("#btn_bump"); pg.wait_for_timeout(1500); report("bump after reconnect", s)
    print("  counter:", pg.query_selector("#counter").inner_text())
    s = len(frames); LAB["l"] = "nav_after"
    pg.click("#nav_about"); pg.wait_for_timeout(1800); report("nav after reconnect", s)
    pg.screenshot(path=OUT + "/reconnect.png")
    b.close()
print("\nCONSOLE err/warn:", [c for c in console if c[1] in ("error", "warning")])
print("PAGEERRORS:", errs)
