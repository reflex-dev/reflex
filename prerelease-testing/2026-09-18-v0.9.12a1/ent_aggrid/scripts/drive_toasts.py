"""Per-route check for the user-facing 'An error occurred' toast caused by the
failed hydrate delta (rxe lambda serialization of FormatterState.cols_defs)."""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
SHOTS = Path(sys.argv[2]); SHOTS.mkdir(parents=True, exist_ok=True)
ROUTES = ["/", "/editable", "/tree", "/pivot", "/model", "/state-grid", "/formatters"]
out = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 1400, "height": 950})
    page = ctx.new_page()
    for r in ROUTES:
        page.goto(BASE + r, wait_until="load", timeout=60000)
        page.wait_for_timeout(5000)
        toasts = page.locator("[data-sonner-toast]")
        out[r] = {
            "toast_count": toasts.count(),
            "toast_texts": [t.inner_text().replace("\n", " ")[:140] for t in toasts.all()],
        }
        if toasts.count():
            page.screenshot(path=str(SHOTS / f"toast_{r.strip('/').replace('/','_') or 'index'}.png"))
        print(r, out[r])
    ctx.close(); b.close()
(SHOTS/"toast_report.json").write_text(json.dumps(out, indent=2))
