"""Print the substate keys of every delta the backend pushes on page load."""
import json, re, sys
from playwright.sync_api import sync_playwright

BASE = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else None
frames = []
with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    page = br.new_context().new_page()
    page.on("websocket", lambda ws: ws.on("framereceived", lambda pl: frames.append(str(pl))))
    page.goto(BASE, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(6000)
    br.close()
for i, f in enumerate(frames):
    if '"delta"' not in f:
        continue
    payload = json.loads(f.split(",", 1)[1])[1]
    print(f"delta frame {i}: substates = {list(payload['delta'])}")
    for sub, vars_ in payload["delta"].items():
        if "oidc" in sub or "iframed" in sub:
            print(f"   {sub}: {json.dumps(vars_)[:300]}")
if OUT:
    open(OUT, "w").write(json.dumps(frames, indent=1))
    print("saved", OUT)
