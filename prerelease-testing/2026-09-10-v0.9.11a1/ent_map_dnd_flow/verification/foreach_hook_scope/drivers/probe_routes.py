"""Load a list of routes and report console/page errors + a marker count.

Usage: probe_routes.py BASE OUTPREFIX route:selector [route:selector ...]
"""

import json
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
OUT = sys.argv[2]
SPECS = sys.argv[3:]

res = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for spec in SPECS:
        route, _, sel = spec.partition("|")
        key = route.strip("/") or "root"
        ctx = b.new_context(viewport={"width": 900, "height": 700})
        page = ctx.new_page()
        errs, perrs = [], []
        page.on(
            "console",
            lambda m: errs.append(f"{m.type}: {m.text}") if m.type == "error" else None,
        )
        page.on("pageerror", lambda e: perrs.append(str(e)))
        try:
            page.goto(BASE + route, wait_until="networkidle", timeout=60000)
        except Exception as e:  # noqa: BLE001
            perrs.append(f"GOTO_FAILED: {e}")
        page.wait_for_timeout(3000)
        res[key] = {
            "matches": page.locator(sel).count() if sel else None,
            "body_text": (page.locator("body").inner_text() or "").replace("\n", " | ")[
                :260
            ],
            "console_errors": errs[:8],
            "page_errors": perrs[:8],
        }
        page.screenshot(path=f"{OUT}_{key}.png")
        ctx.close()
    b.close()
print(json.dumps(res, indent=2))
