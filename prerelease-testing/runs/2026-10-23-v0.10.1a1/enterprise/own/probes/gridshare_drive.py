"""Drive own/gridshare: after every in-place op the two AG Grids and the foreach must equal the backend rows (#json).

Usage: gridshare_drive.py <frontend_base> <label>
"""
import json
import os
import sys
import time
from pathlib import Path

import playwright  # noqa: F401
from playwright.sync_api import sync_playwright

assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in playwright.__file__, playwright.__file__
BASE, LABEL = sys.argv[1].rstrip("/"), sys.argv[2]
OUT = Path(__file__).resolve().parent.parent / "out"
OUT.mkdir(exist_ok=True)
# rxe.ag_grid's `id` prop is the grid handle, not a DOM id: take the n-th .ag-root-wrapper (0 = ga, 1 = gb)
JS_ROWS = """(idx) => { const w = document.querySelectorAll('.ag-root-wrapper')[idx]; if (!w) return null;
 const seen = {}; for (const r of w.querySelectorAll('.ag-row')) { const i = +r.getAttribute('row-index'); if (seen[i]) continue;
   const cell = (c) => r.querySelector('[col-id=' + c + ']'); if (!cell('uid')) continue;
   seen[i] = {i, id: r.getAttribute('row-id'), uid: cell('uid').innerText, name: cell('name').innerText, price: cell('price').innerText}; }
 return Object.values(seen).sort((a,b)=>a.i-b.i); }"""
checks = []


def check(name, ok, info=None):
    checks.append({"name": name, "ok": bool(ok), "info": info})
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f": {json.dumps(info, default=str)[:400]}"))


def snapshot(p):
    state = json.loads(p.locator("#json").inner_text())
    ga = p.evaluate(JS_ROWS, 0)
    gb = p.evaluate(JS_ROWS, 1)
    fe = [t.split(":") for t in p.locator(".fe-row").all_inner_texts()]
    return state, ga, gb, fe


def same(state, grid):
    return grid is not None and [(r["uid"], r["name"], str(r["price"])) for r in state] == [(r["uid"], r["name"], r["price"]) for r in grid]


def settle(p, want_log, timeout=8):
    end = time.time() + timeout
    while time.time() < end:
        if p.locator("#log").inner_text().endswith(want_log):
            p.wait_for_timeout(400)
            return True
        p.wait_for_timeout(100)
    return False


def verify(p, label):
    state, ga, gb, fe = snapshot(p)
    check(f"{label}: grid A (row_id_key) == state", same(state, ga), {"state": state, "ga": ga})
    check(f"{label}: grid B (index ids) == state", same(state, gb), {"state": state, "gb": gb})
    check(f"{label}: foreach == state", [(r["uid"], r["name"], str(r["price"])) for r in state] == [tuple(x) for x in fe], {"state": state, "fe": fe})
    total = p.locator("#total").inner_text()
    check(f"{label}: total == sum", total == f"total={sum(int(r['price']) for r in state)}", total)


def main():
    errors = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        p = b.new_page()
        p.on("pageerror", lambda e: errors.append(f"pageerror: {str(e)[:200]}"))
        p.on("console", lambda m: m.type == "error" and not m.text.startswith("***") and errors.append(f"console: {m.text[:200]}"))
        p.goto(BASE + "/", wait_until="networkidle")
        p.wait_for_selector(".ag-root-wrapper .ag-row", timeout=30000)
        p.locator("#reset_rows").click(); settle(p, "", 5); p.wait_for_timeout(500)
        verify(p, "initial")
        for op in ["bump_first", "sort_price", "reverse", "add_row", "remove_first", "rename_all", "sort_price", "bump_first"]:
            p.locator(f"#{op}").click()
            settle(p, op)
            verify(p, op)
        # cell edit in grid A: price of the first row -> 777
        cell = p.locator(".ag-root-wrapper").nth(0).locator(".ag-row[row-index='0'] [col-id=price]").first
        cell.dblclick(); p.keyboard.press("Control+A"); p.keyboard.type("777"); p.keyboard.press("Enter")
        settle(p, "=777")
        verify(p, "cell edit grid A -> 777")
        p.locator("#swap_cols").click(); settle(p, "swap_cols")
        hdr = p.evaluate("() => [...document.querySelectorAll('.ag-root-wrapper')[0].querySelectorAll('.ag-header-cell-text')].map(e=>e.innerText)")
        check("swap_cols: grid A header order follows in-place list swap", [h.lower() for h in hdr] == ["uid", "price", "name"], hdr)
        p.reload(wait_until="networkidle"); p.wait_for_selector(".ag-root-wrapper .ag-row", timeout=30000); p.wait_for_timeout(800)
        verify(p, "after reload")
        b.close()
    ok = sum(1 for c in checks if c["ok"])
    json.dump({"checks": checks, "errors": errors}, open(OUT / f"gridshare_{LABEL}.json", "w"), indent=1)
    print(f"SUMMARY {LABEL} gridshare: {ok}/{len(checks)} pass; errors={errors[:5]}")


main()
