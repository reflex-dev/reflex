"""EN-1 minimal driver: edit a cell in an editable AG Grid; compare backend json, store (#raw), memo, chart, grid C, foreach."""
import json
import os
import sys

import playwright  # noqa: F401
from playwright.sync_api import sync_playwright

assert "/envs/driver/" in playwright.__file__
BASE, LABEL, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
GRID = """(idx) => { const w = document.querySelectorAll('.ag-root-wrapper')[idx]; const o = {};
  for (const r of w.querySelectorAll('.ag-row')) { const u = r.querySelector('[col-id=uid]'); const p = r.querySelector('[col-id=price]'); if (u && p) o[u.innerText] = p.innerText; } return o; }"""
BARS = """() => [...document.querySelectorAll('.recharts-bar-rectangle path, .recharts-bar-rectangle rect')].map(e => e.getAttribute('height') || e.getAttribute('d'))"""


def snap(p):
    return {
        "backend": json.loads(p.locator("#json").inner_text()),
        "store_raw": p.locator("#raw").inner_text(),
        "memo": p.locator("#memo").inner_text(),
        "gridA": p.evaluate(GRID, 0),
        "gridC": p.evaluate(GRID, 1),
        "bars": p.evaluate(BARS),
        "foreach": p.locator(".fe-row").all_inner_texts(),
        "log": p.locator("#log").inner_text(),
    }


def edit(p, idx, uid, val):
    w = p.locator(".ag-root-wrapper").nth(idx)
    w.locator(f".ag-row[row-id='{uid}'] [col-id=price]").first.dblclick()
    p.keyboard.press("Control+A"); p.keyboard.type(val); p.keyboard.press("Enter")
    try:
        p.wait_for_function(f"() => document.querySelector('#log').innerText.includes('{uid}={val}')", timeout=10000)
    except Exception:
        print("EDIT-TIMEOUT log=", p.locator('#log').inner_text(), "rows=", p.evaluate("() => [...document.querySelectorAll('.ag-row')].map(r=>r.getAttribute('row-id'))"))
        p.screenshot(path=OUT + ".png")
    p.wait_for_timeout(1000)


res = {}
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    p = b.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(BASE, wait_until="networkidle"); p.wait_for_selector(".ag-root-wrapper .ag-row", timeout=60000); p.wait_for_timeout(1500)
    res["initial"] = snap(p)
    edit(p, 0, "u-2", "777")
    res["after_edit_A_777"] = snap(p)
    p.locator("#reset").click(); p.wait_for_function("() => document.querySelector('#log').innerText === ''"); p.wait_for_timeout(1000)
    res["after_reset"] = snap(p)
    edit(p, 1, "u-2", "500")
    res["after_clamp_C_500"] = snap(p)
    res["errors"] = errs
    b.close()
json.dump(res, open(OUT, "w"), indent=1)
for k, v in res.items():
    print(k, json.dumps(v)[:600])
