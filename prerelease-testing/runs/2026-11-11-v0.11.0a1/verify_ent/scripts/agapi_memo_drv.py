"""Issue 3 memo variant driver. Usage: agapi_memo_drv.py <frontend url> <label>"""

import json
import sys

import playwright
from playwright.sync_api import sync_playwright

assert "/envs/driver/" in playwright.__file__, playwright.__file__
U, L = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.goto(U)
    pg.wait_for_selector(".ag-row", timeout=90000)
    pg.wait_for_timeout(1500)
    pg.click("#select-memo"); pg.wait_for_timeout(1500)
    n = pg.locator(".ag-row-selected").count()
    b.close()
print("[PASS]" if n == 3 else "[FAIL]", L, json.dumps({"rows_selected_via_memo_button": n}))
