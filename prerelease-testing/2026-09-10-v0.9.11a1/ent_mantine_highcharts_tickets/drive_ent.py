"""Generic enterprise-demo driver: render, interact, capture anomalies.

Usage: python drive_ent.py <frontend_port> <out.json> [routes...]
"""

import json
import sys

from playwright.sync_api import sync_playwright

PORT = int(sys.argv[1])
OUT = sys.argv[2]
ROUTES = sys.argv[3:] or ["/"]
BASE = f"http://localhost:{PORT}"
R = {"routes": {}, "console": [], "pageerrors": [], "failed": [], "http_errors": []}

COUNTS = """() => ({
  svg: document.querySelectorAll('svg').length,
  buttons: document.querySelectorAll('button').length,
  inputs: document.querySelectorAll('input').length,
  rows: document.querySelectorAll('tbody tr, .ag-row').length,
  highcharts: document.querySelectorAll('.highcharts-container').length,
  mantine: document.querySelectorAll('[class*="mantine-"]').length,
  canvas: document.querySelectorAll('canvas').length,
  text_len: document.body.innerText.length,
})"""

with sync_playwright() as p:
    br = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
    page = br.new_context().new_page()
    page.on("console", lambda m: R["console"].append({"type": m.type, "text": m.text[:250]}))
    page.on("pageerror", lambda e: R["pageerrors"].append(str(e)[:250]))
    page.on("requestfailed", lambda r: R["failed"].append({"url": r.url[:150], "err": str(r.failure)[:100]}))
    page.on("response", lambda r: R["http_errors"].append({"url": r.url[:150], "status": r.status})
            if r.status >= 400 else None)

    for route in ROUTES:
        page.goto(BASE + route, wait_until="networkidle")
        page.wait_for_timeout(3500)
        rec = {"url": page.url, "before": page.evaluate(COUNTS),
               "text": page.locator("body").inner_text()[:400]}
        # click up to six enabled buttons, recording the resulting counts
        clicks = []
        n = min(page.locator("button:visible").count(), 6)
        for i in range(n):
            try:
                b = page.locator("button:visible").nth(i)
                label = (b.inner_text() or "")[:30]
                b.click(timeout=3000)
                page.wait_for_timeout(700)
                clicks.append({"i": i, "label": label, "counts": page.evaluate(COUNTS)})
            except Exception as e:  # noqa: BLE001
                clicks.append({"i": i, "err": f"{type(e).__name__}"})
        rec["clicks"] = clicks
        rec["after"] = page.evaluate(COUNTS)
        R["routes"][route] = rec
        print(f"[{route}] " + json.dumps({k: rec[k] for k in ("before", "after")}, default=str)[:300], flush=True)

    R["console_errors"] = [c for c in R["console"] if c["type"] == "error"]
    br.close()

with open(OUT, "w") as f:
    json.dump(R, f, indent=1)
print("CONSOLE ERRORS:", json.dumps(R["console_errors"])[:1200])
print("PAGE ERRORS:", json.dumps(R["pageerrors"])[:800])
print("FAILED:", json.dumps(R["failed"])[:500])
print("HTTP>=400:", json.dumps(R["http_errors"])[:600])
print("saved", OUT)
