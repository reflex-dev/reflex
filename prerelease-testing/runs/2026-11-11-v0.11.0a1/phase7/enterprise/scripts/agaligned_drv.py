"""Issue 3 aligned_grids driver: resize a column in the top grid, check the bottom grid follows.

Usage: agaligned_drv.py <frontend url> <label>
"""

import json
import sys

import playwright
from playwright.sync_api import sync_playwright

assert "/envs/driver/" in playwright.__file__, playwright.__file__
U, L = sys.argv[1], sys.argv[2]
out = {"page_errors": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page()
    pg.on("pageerror", lambda e: out["page_errors"].append(str(e)[:300]))
    pg.goto(U)
    pg.wait_for_selector(".ag-row", timeout=90000)
    pg.wait_for_timeout(2000)
    w = lambda i: pg.evaluate(f"document.querySelectorAll('.ag-root-wrapper')[{i}].querySelector('.ag-header-cell[col-id=make]').getBoundingClientRect().width")
    out["before"] = [w(0), w(1)]
    h = pg.locator(".ag-root-wrapper").nth(0).locator(".ag-header-cell[col-id=make] .ag-header-cell-resize")
    bb = h.bounding_box()
    pg.mouse.move(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2)
    pg.mouse.down(); pg.mouse.move(bb["x"] + 80, bb["y"] + bb["height"] / 2, steps=10); pg.mouse.up()
    pg.wait_for_timeout(1500)
    out["after"] = [w(0), w(1)]
    b.close()
ok = abs(out["after"][0] - out["before"][0]) > 30 and abs(out["after"][0] - out["after"][1]) < 2
print("[PASS]" if ok else "[FAIL]", L, json.dumps(out))
