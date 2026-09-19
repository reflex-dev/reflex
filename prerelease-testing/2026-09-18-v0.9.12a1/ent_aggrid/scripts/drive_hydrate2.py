"""After a reload, click the row counter once: does it continue from the server value?"""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
SHOTS = Path(sys.argv[2]); SHOTS.mkdir(parents=True, exist_ok=True)
out = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 1400, "height": 900})
    page = ctx.new_page()
    page.goto(BASE + "/formatters", wait_until="load", timeout=60000)
    page.wait_for_selector(".ag-cell button", timeout=30000); page.wait_for_timeout(2500)
    btn = lambda: page.locator(".ag-cell button").first
    out["initial"] = btn().inner_text()
    for i in range(3):
        btn().click(); page.wait_for_timeout(800)
    out["after_3_clicks"] = btn().inner_text()
    page.reload(wait_until="load", timeout=60000)
    page.wait_for_selector(".ag-cell button", timeout=30000); page.wait_for_timeout(4000)
    out["after_reload"] = btn().inner_text()
    btn().click(); page.wait_for_timeout(1500)
    out["after_reload_plus_one_click"] = btn().inner_text()
    page.screenshot(path=str(SHOTS/"hydrate_04_reload_plus_click.png"))
    ctx.close(); b.close()
print(json.dumps(out, indent=2))
(SHOTS/"hydrate_report2.json").write_text(json.dumps(out, indent=2))
