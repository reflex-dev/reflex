"""Edit cells in the AG Grids; snapshot backend, store, memo, every grid and foreach after each step."""
import json
import sys

import playwright  # noqa: F401
from playwright.sync_api import sync_playwright

assert "/envs/driver/" in playwright.__file__
BASE, OUT = sys.argv[1], sys.argv[2]
GRIDS = ["ga", "gc", "gr", "gb"]
GRID = """(idx) => { const w = document.querySelectorAll('.ag-root-wrapper')[idx]; const o = {};
  for (const r of w.querySelectorAll('.ag-row')) { const u = r.querySelector('[col-id=uid]'); if (!u || o[u.innerText]) continue;
    o[u.innerText] = [r.querySelector('[col-id=price]')?.innerText, r.querySelector('[col-id="addr.city"]')?.innerText]; } return o; }"""


def snap(p):
    s = {"backend": json.loads(p.locator("#json").inner_text()), "store": json.loads(p.locator("#raw").inner_text()),
         "memo": json.loads(p.locator("#memo").inner_text()), "foreach": p.locator(".fe-row").all_inner_texts(),
         "log": p.locator("#log").inner_text()}
    for i, g in enumerate(GRIDS):
        s[g] = p.evaluate(GRID, i)
    return s


def edit(p, gi, uid, col, val):
    w = p.locator(".ag-root-wrapper").nth(gi)
    w.locator(f".ag-row[row-id='{uid}'] [col-id='{col}']").first.dblclick()
    p.keyboard.press("Control+A"); p.keyboard.type(val); p.keyboard.press("Enter")
    try:
        p.wait_for_function(f"() => document.querySelector('#log').innerText.includes('{uid}={val}')", timeout=10000)
    except Exception:
        return False
    p.wait_for_timeout(1200)
    return True


def verdict(s, uid, price, city):
    """Which views show (price, city) for uid."""
    want = [str(price), city]
    out = {"backend": [str(x) for x in [next(r for r in s["backend"] if r["uid"] == uid)["price"], next(r for r in s["backend"] if r["uid"] == uid)["addr"]["city"]]] == want}
    for k in ("store", "memo"):
        r = next(r for r in s[k] if r["uid"] == uid)
        out[k] = [str(r["price"]), r["addr"]["city"]] == want
    for g in GRIDS:
        out[g] = s[g].get(uid) == want
    out["foreach"] = f"{uid}:{price}:{city}" in s["foreach"]
    return out


steps = []
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    p = b.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(BASE, wait_until="networkidle"); p.wait_for_selector(".ag-root-wrapper .ag-row", timeout=60000); p.wait_for_timeout(1500)

    def step(name, gi, uid, col, val, expect, expect_all):
        ok = edit(p, gi, uid, col, val)
        s = snap(p)
        v = verdict(s, uid, *expect)
        steps.append({"step": name, "edit_reached_backend": ok, "views_showing_expected": v,
                      "all_expected_views_ok": all(v[k] for k in expect_all), "snap": s})
        print(f"{name}: reached={ok} " + " ".join(f"{k}={'Y' if x else 'n'}" for k, x in v.items()))

    ALL = ["backend", "store", "memo", "ga", "gc", "gr", "gb", "foreach"]
    step("A price u-2 -> 777 (handler stores as typed)", 0, "u-2", "price", "777", (777, "rome"), ALL)
    step("A nested addr.city u-3 -> paris", 0, "u-3", "addr.city", "paris", (50, "paris"), ALL)
    step("C price u-1 -> 500 (handler clamps to 100)", 1, "u-1", "price", "500", (100, "oslo"), ALL)
    step("R price u-2 -> 5 (handler rejects, keeps 777)", 2, "u-2", "price", "5", (777, "rome"), [k for k in ALL if k != "gr"])
    p.locator("#reset").click(); p.wait_for_timeout(1500)
    s = snap(p)
    steps.append({"step": "reset", "views_showing_expected": verdict(s, "u-2", 10, "rome"), "snap": s})
    print("reset:", " ".join(f"{k}={'Y' if x else 'n'}" for k, x in steps[-1]["views_showing_expected"].items()))
    p.reload(wait_until="networkidle"); p.wait_for_selector(".ag-root-wrapper .ag-row"); p.wait_for_timeout(1200)
    step("after reload: A price u-2 -> 778", 0, "u-2", "price", "778", (778, "rome"), ALL)
    b.close()
json.dump({"steps": steps, "page_errors": errs}, open(OUT, "w"), indent=1)
print("page_errors:", errs[:3])
