"""Driver for deapp: after each mutation, sweep the mouse over the state-backed grid and click a cell; count page errors.

Usage: drive_deapp.py <base url> <out dir> <label>
"""

import json
import os
import sys
import time

assert "/envs/driver/" in sys.executable, sys.executable
from playwright.sync_api import sync_playwright  # noqa: E402

BASE, OUT, LABEL = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
res = {"label": LABEL, "steps": [], "console": [], "page_errors": []}


def wait_text(page, sel, pred, timeout=8.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            t = page.inner_text(sel)
            if pred(t):
                return t
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.2)
    try:
        return page.inner_text(sel)
    except Exception:  # noqa: BLE001
        return None


def sweep(page):
    """Hover over every row of the state grid, then click the first cell of the last row."""
    box = page.locator("#de_state canvas").first.bounding_box()
    for y in range(10, int(box["height"]) - 5, 12):
        page.mouse.move(box["x"] + 30, box["y"] + y)
        time.sleep(0.02)
    page.mouse.click(box["x"] + 30, box["y"] + 36)
    time.sleep(0.6)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_page()
    page.on("console", lambda m: res["console"].append({"type": m.type, "text": m.text[:300]}) if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: res["page_errors"].append(str(e)[:300]))
    page.goto(BASE, wait_until="load", timeout=120000)
    wait_text(page, "#nrows", lambda s: s.strip() == "3", 30)

    def step(name, action, expect_rows=None):
        before = len(res["page_errors"])
        action()
        if expect_rows is not None:
            wait_text(page, "#nrows", lambda s: s.strip() == str(expect_rows))
        try:
            sweep(page)
        except Exception as e:  # noqa: BLE001
            res["steps"].append({"step": name, "error": repr(e)})
        n = len(res["page_errors"]) - before
        cell = page.inner_text("#cell") if page.locator("#cell").count() else None
        res["steps"].append({"step": name, "new_page_errors": n, "nrows": page.inner_text("#nrows"), "ncols": page.inner_text("#ncols"), "cell": cell, "canvas": page.locator("#de_state canvas").count()})
        print(f"[{'OK ' if n == 0 else 'ERR'}] {name}: page_errors+{n} nrows={page.inner_text('#nrows')} ncols={page.inner_text('#ncols')} cell={cell}")

    step("initial sweep", lambda: None)
    step("append (in-place) -> 4 rows", lambda: page.click("#append"), 4)
    step("append again -> 5 rows", lambda: page.click("#append"), 5)
    step("assign (new list) -> 6 rows", lambda: page.click("#assign"), 6)
    step("more_cols (in-place column append + data reassign)", lambda: page.click("#more_cols"))
    step("reset -> 3 rows", lambda: page.click("#reset"), 3)
    step("append after reset -> 4 rows", lambda: page.click("#append"), 4)
    page.screenshot(path=f"{OUT}/{LABEL}-end.png", full_page=True)
    page.reload(wait_until="load")
    wait_text(page, "#nrows", lambda s: s.strip() in ("3", "4"), 30)
    step("after reload sweep", lambda: None)
    browser.close()

with open(f"{OUT}/{LABEL}.json", "w") as f:
    json.dump(res, f, indent=1)
print(f"== {LABEL}: page_errors={len(res['page_errors'])} unique={sorted(set(e[:80] for e in res['page_errors']))}")
