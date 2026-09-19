"""Check whether the failed hydrate delta (rxe lambda serialization) loses session state.

Usage: python drive_hydrate.py <base_url> <shots_dir>

Clicks the /formatters row-counter button twice (server-side state), reloads the page,
and reports whether the count survives the reload (i.e. whether the hydrate delta landed).
Also checks is_hydrated-dependent behaviour on a page WITHOUT the lambda state var.
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
SHOTS = Path(sys.argv[2])
SHOTS.mkdir(parents=True, exist_ok=True)
out = {}

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 1400, "height": 900})
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)[:300]))

    page.goto(BASE + "/formatters", wait_until="load", timeout=60000)
    page.wait_for_selector(".ag-cell button", timeout=30000)
    page.wait_for_timeout(2000)
    btn = page.locator(".ag-cell button").first
    out["before_clicks"] = btn.inner_text()
    btn.click()
    page.wait_for_timeout(900)
    btn.click()
    page.wait_for_timeout(1500)
    out["after_clicks"] = page.locator(".ag-cell button").first.inner_text()
    page.screenshot(path=str(SHOTS / "hydrate_01_after_clicks.png"))

    page.reload(wait_until="load", timeout=60000)
    page.wait_for_selector(".ag-cell button", timeout=30000)
    page.wait_for_timeout(4000)
    out["after_reload"] = page.locator(".ag-cell button").first.inner_text()
    page.screenshot(path=str(SHOTS / "hydrate_02_after_reload.png"))

    # client-side nav away and back (no full reload -> pure delta path)
    page.goto(BASE + "/editable", wait_until="load", timeout=60000)
    page.wait_for_timeout(2000)
    page.goto(BASE + "/formatters", wait_until="load", timeout=60000)
    page.wait_for_selector(".ag-cell button", timeout=30000)
    page.wait_for_timeout(3000)
    out["after_nav_back"] = page.locator(".ag-cell button").first.inner_text()
    page.screenshot(path=str(SHOTS / "hydrate_03_after_nav_back.png"))

    # is_hydrated probe: read the reflex client state from the page
    out["is_hydrated_probe"] = page.evaluate(
        "() => { try { return JSON.stringify(Object.keys(window).filter(k => k.toLowerCase().includes('reflex'))); } catch(e) { return 'err:'+e; } }"
    )
    out["pageerrors"] = errs
    ctx.close()
    b.close()

print(json.dumps(out, indent=2))
(SHOTS / "hydrate_report.json").write_text(json.dumps(out, indent=2))
