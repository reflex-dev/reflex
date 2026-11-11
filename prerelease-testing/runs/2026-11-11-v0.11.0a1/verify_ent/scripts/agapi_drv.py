"""Issue 3 driver: click grid.api.select_all() / AgGridAPI.create(id).select_all() / getSelectedRows(callback) and report.

Usage: agapi_drv.py <frontend url> <label> <shot dir>
"""

import json
import sys

import playwright
from playwright.sync_api import sync_playwright

assert "/envs/driver/" in playwright.__file__, playwright.__file__
U, L, SHOTS = sys.argv[1], sys.argv[2], sys.argv[3]
out = {"console": [], "page_errors": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("console", lambda m: out["console"].append(f"{m.type}: {m.text[:200]}") if m.type in ("error", "warning") and "AG Grid" not in m.text and "****" not in m.text else None)
    pg.on("pageerror", lambda e: out["page_errors"].append(str(e)[:300]))
    pg.goto(U)
    pg.wait_for_selector(".ag-row", timeout=90000)
    pg.wait_for_timeout(1500)
    pg.click("#select-all"); pg.wait_for_timeout(1500)
    out["rows_after_grid_api"] = pg.locator(".ag-row-selected").count()
    pg.click("#read"); pg.wait_for_timeout(1500)
    out["state_selected"] = pg.locator("#selected").inner_text()
    pg.reload(); pg.wait_for_selector(".ag-row", timeout=90000); pg.wait_for_timeout(1500)
    pg.click("#select-all-2"); pg.wait_for_timeout(1500)
    out["rows_after_AgGridAPI_create"] = pg.locator(".ag-row-selected").count()
    out["typeof_refs_in_window"] = pg.evaluate("typeof window.refs")
    pg.screenshot(path=f"{SHOTS}/agapi_{L}.png")
    b.close()
ok = out["rows_after_grid_api"] == 3 and out["state_selected"] == "3" and out["rows_after_AgGridAPI_create"] == 3
print(("[PASS]" if ok else "[FAIL]"), L, json.dumps(out)[:1500])
