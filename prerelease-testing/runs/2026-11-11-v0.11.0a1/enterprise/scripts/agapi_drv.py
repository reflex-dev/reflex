"""Drive the agapi repro: click select all, read selection; print console/page errors.

Usage: agapi_drv.py <url> <label>
"""
import json, sys, time
import playwright
from playwright.sync_api import sync_playwright
assert "/envs/driver/" in playwright.__file__
U, L = sys.argv[1], sys.argv[2]
out = {"console": [], "page_errors": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("console", lambda m: out["console"].append(f"{m.type}: {m.text[:200]}") if m.type in ("error", "warning") and "AG Grid" not in m.text and "****" not in m.text else None)
    pg.on("pageerror", lambda e: out["page_errors"].append(str(e)[:300]))
    pg.goto(U)
    pg.wait_for_selector(".ag-row", timeout=60000)
    pg.wait_for_timeout(1500)
    for btn in ("#select-all", "#read"):
        pg.click(btn); pg.wait_for_timeout(1500)
    sel_rows = pg.locator(".ag-row-selected").count()
    out["selected_rows_dom"] = sel_rows
    out["state_selected"] = pg.locator("#selected").inner_text()
    pg.screenshot(path=f"/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad/apps/enterprise/shots/agapi_{L}.png")
    b.close()
ok = out["selected_rows_dom"] == 3 and out["state_selected"] == "3"
print(("[PASS]" if ok else "[FAIL]"), L, json.dumps(out)[:1500])
