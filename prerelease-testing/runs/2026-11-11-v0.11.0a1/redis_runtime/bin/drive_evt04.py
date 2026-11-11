"""EVT-04 re-verify: prod + Redis + default workers; 6 Chromium tabs (own tokens) each start a background task
(bg_incr 50) and receive 10 cross-worker app.modify_state updates (/api/bump on fresh connections).
Usage: $SB/envs/driver/bin/python drive_evt04.py BASE OUT_JSON"""
import json, sys, time, urllib.request
from playwright.sync_api import sync_playwright
assert "/envs/driver/" in sys.executable
base, out = sys.argv[1].rstrip("/"), sys.argv[2]
R = {"tabs": [], "console": []}
def post(path):
    req = urllib.request.Request(base + path, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pages = []
    for i in range(6):
        ctx = b.new_context(); pg = ctx.new_page()
        pg.on("console", lambda m: R["console"].append(f"{m.type}: {m.text[:200]}") if m.type in ("error", "warning") else None)
        pg.goto(base + "/", wait_until="networkidle", timeout=120000); pg.wait_for_selector("#count")
        pages.append(pg)
    time.sleep(1.5)
    for pg in pages:
        pg.click("#bg")
    pids = []
    for pg in pages:
        tok = pg.evaluate("() => sessionStorage.getItem('token')")
        for _ in range(10):
            pids.append(post(f"/api/bump?token={tok}&n=1")["pid"])
    time.sleep(4)
    for i, pg in enumerate(pages):
        t = {"tab": i, "bg_count": pg.inner_text("#bg_count"), "api_count": pg.inner_text("#api_count"), "count": pg.inner_text("#count"), "pid": pg.inner_text("#pid")}
        t["ok"] = t["bg_count"] == "50" and t["api_count"] == "10" and t["count"] == "60"
        R["tabs"].append(t)
    pages[0].screenshot(path=out.replace(".json", ".png"))
    b.close()
R["api_worker_pids"] = sorted(set(pids)); R["ok"] = sum(t["ok"] for t in R["tabs"])
R["console"] = [c for c in R["console"] if "Hey developer" not in c and "favicon" not in c]
open(out, "w").write(json.dumps(R, indent=1)); print(json.dumps({k: R[k] for k in ("ok", "api_worker_pids")}), R["tabs"], R["console"][:5])
