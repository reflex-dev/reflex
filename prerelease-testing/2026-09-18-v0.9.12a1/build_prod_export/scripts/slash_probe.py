"""Check prod trailing-slash rewriting + router.url.path for query-string URLs.

Usage: python slash_probe.py <base_url> <label> <out_json>
"""

import json
import sys

from playwright.sync_api import sync_playwright

BASE, LABEL, OUT = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
PATHS = ["/app/about?q=hello", "/app/apple?q=hello", "/app/items/7?x=1", "/app/about"]
res = {"label": LABEL, "base": BASE, "results": []}

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for p in PATHS:
        ctx = b.new_context()
        page = ctx.new_page()
        bad = []
        page.on("response", lambda r: bad.append((r.url, r.status)) if r.status >= 400 else None)
        r = page.goto(BASE + p, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(1500)
        entry = {"requested": p, "http_status": r.status if r else None, "final_url": page.url}
        try:
            entry["router_path_text"] = page.locator("#router-path").first.inner_text(timeout=2000)
        except Exception:  # noqa: BLE001
            entry["router_path_text"] = None
        entry["location_pathname"] = page.evaluate("location.pathname + location.search")
        entry["bad"] = bad
        res["results"].append(entry)
        ctx.close()
    b.close()

with open(OUT, "w") as f:
    json.dump(res, f, indent=2)
print(json.dumps(res, indent=2))
