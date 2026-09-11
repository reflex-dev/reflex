"""Two final checks on the ag_grid demo dev server:
1. /aligned-grids horizontal scroll synchronisation (real wheel events).
2. Hot reload: the driver waits for an external source edit and reports what the page shows.

Usage: python drive_aligned_hmr.py <base_url> <shots_dir> <mode>
  mode=aligned  -> scroll sync check
  mode=hmr_before / hmr_after -> read the /editable page heading text
"""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/"); SHOTS = Path(sys.argv[2]); SHOTS.mkdir(parents=True, exist_ok=True)
MODE = sys.argv[3]
out = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 1200, "height": 900}); page = ctx.new_page()
    errs = []; page.on("pageerror", lambda e: errs.append(str(e)[:300]))
    if MODE == "aligned":
        page.goto(BASE + "/aligned-grids", wait_until="load", timeout=60000)
        page.wait_for_selector(".ag-cell", timeout=40000); page.wait_for_timeout(2500)
        out["viewports"] = page.locator(".ag-body-horizontal-scroll-viewport").count()
        out["before"] = page.eval_on_selector_all(
            ".ag-body-horizontal-scroll-viewport", "els => els.map(e => e.scrollLeft)")
        # real wheel over the first grid body
        body = page.locator(".ag-body-viewport").first
        bb = body.bounding_box()
        page.mouse.move(bb["x"] + bb["width"]/2, bb["y"] + bb["height"]/2)
        for _ in range(6):
            page.mouse.wheel(200, 0)
            page.wait_for_timeout(200)
        page.wait_for_timeout(1200)
        out["after"] = page.eval_on_selector_all(
            ".ag-body-horizontal-scroll-viewport", "els => els.map(e => e.scrollLeft)")
        out["synced"] = bool(out["after"]) and len(set(out["after"])) == 1 and out["after"][0] > 0
        page.screenshot(path=str(SHOTS/"aligned_wheel_sync.png"))
    else:
        page.goto(BASE + "/editable", wait_until="load", timeout=60000)
        page.wait_for_selector(".ag-cell", timeout=40000); page.wait_for_timeout(2500)
        out["body_text_head"] = page.locator("body").inner_text()[:220].replace("\n", " | ")
        out["headers"] = [h.inner_text() for h in page.locator(".ag-header-cell-text").all()]
        page.screenshot(path=str(SHOTS/f"{MODE}.png"))
    out["pageerrors"] = errs
    ctx.close(); b.close()
print(json.dumps(out, indent=2))
(SHOTS/f"{MODE}_report.json").write_text(json.dumps(out, indent=2))
