"""Isolate: does an auth=True, cache=False computed var whose value changed while
withheld ever reach the browser after login, without a manual reload?

Usage: python uncached_after_login.py <frontend_port> <label> <idp_port>
"""
import json, os, sys
from playwright.sync_api import sync_playwright
PORT, LABEL, IDP = int(sys.argv[1]), sys.argv[2], sys.argv[3]
BASE = f"http://localhost:{PORT}"
OUT = {"label": LABEL, "steps": [], "console": [], "pageerrors": [], "http_errors": []}
def rec(n, **kw):
    OUT["steps"].append({"step": n, **kw}); print(f"[{n}] " + json.dumps(kw, default=str)[:300], flush=True)
def t(pg, sel):
    try: return pg.locator(sel).first.inner_text(timeout=4000)
    except Exception as e: return f"<absent:{type(e).__name__}>"
def snap(pg): return {"shared": t(pg, "#shared-label"), "secret": t(pg, "#secret-label"), "email": t(pg, "#email"), "hits": t(pg, "#hits")}
with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    ctx = br.new_context(); pg = ctx.new_page()
    pg.on("console", lambda m: OUT["console"].append({"type": m.type, "text": m.text[:200]}))
    pg.on("pageerror", lambda e: OUT["pageerrors"].append(str(e)[:300]))
    pg.on("response", lambda r: OUT["http_errors"].append({"url": r.url[:150], "status": r.status}) if r.status >= 400 else None)
    pg.goto(BASE, wait_until="networkidle"); pg.wait_for_timeout(2000)
    rec("anon_initial", **snap(pg))
    pg.click("#poison-shared"); pg.wait_for_timeout(1200)
    rec("anon_after_poison_shared", **snap(pg))
    pg.goto(f"{BASE}/login", wait_until="networkidle"); pg.wait_for_timeout(1500)
    pg.click("text=Login with Generic"); pg.wait_for_timeout(4000)
    rec("right_after_login", url=pg.url, **snap(pg))
    pg.click("#bump"); pg.wait_for_timeout(1500)
    rec("after_unrelated_event", **snap(pg))
    pg.click("#bump"); pg.wait_for_timeout(1500)
    rec("after_second_event", **snap(pg))
    pg.reload(wait_until="networkidle"); pg.wait_for_timeout(2000)
    rec("after_reload", **snap(pg))
    pg.screenshot(path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shots", f"uncached_{LABEL}.png"))
    br.close()
path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", f"uncached_{LABEL}.json")
json.dump(OUT, open(path, "w"), indent=1); print("wrote", path)
