"""Load / and /memo, report console errors + whether the draggables rendered."""
import json, sys
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
OUT = sys.argv[2]
res = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for route, key in (("/", "raw"), ("/memo", "memo")):
        ctx = b.new_context(viewport={"width": 900, "height": 700})
        page = ctx.new_page()
        errs, perrs = [], []
        page.on("console", lambda m: errs.append(f"{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: perrs.append(str(e)))
        page.goto(BASE + route, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3500)
        res[key] = {
            "draggables": page.locator('[draggable="true"]').count(),
            "body_text": (page.locator("body").inner_text() or "")[:200],
            "console_errors": errs[:8],
            "page_errors": perrs[:8],
        }
        page.screenshot(path=f"{OUT}_{key}.png")
        ctx.close()
    b.close()
print(json.dumps(res, indent=2))
