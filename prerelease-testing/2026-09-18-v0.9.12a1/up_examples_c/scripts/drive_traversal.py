"""Drive the reflex-examples `traversal` app: slider, graph regeneration,
algorithm select, self-chaining async event loop (DFS/BFS) with toasts.

usage: drive_traversal.py <frontend_url> <label> <shots_dir>
"""

import json
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1].rstrip("/")
LABEL = sys.argv[2]
SHOTS = sys.argv[3]

console, page_errors, failed, bad = [], [], [], []
r = {}


def grid_colors(page):
    return page.evaluate(
        """() => Array.from(document.querySelectorAll('div'))
             .filter(d => { const c = getComputedStyle(d);
                            return c.width === '50px' && c.height === '50px'; })
             .map(d => getComputedStyle(d).backgroundColor)"""
    )


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_context(viewport={"width": 1280, "height": 1000}).new_page()
    page.on("console", lambda m: console.append({"type": m.type, "text": m.text}))
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on("requestfailed", lambda q: failed.append(f"{q.method} {q.url} :: {q.failure}"))
    page.on("response", lambda x: bad.append(f"{x.status} {x.url}") if x.status >= 400 else None)

    page.goto(URL + "/", wait_until="networkidle", timeout=90_000)
    page.wait_for_timeout(2500)
    c0 = grid_colors(page)
    r["grid_cells"] = len(c0)
    r["distinct_colors_initial"] = sorted(set(c0))
    page.screenshot(path=f"{SHOTS}/{LABEL}_01_initial.png", full_page=True)

    # Generate a new graph (state mutation over a 2D list under rx.foreach)
    page.get_by_role("button", name="Generate Graph").click()
    page.wait_for_timeout(1500)
    c1 = grid_colors(page)
    r["grid_changed_after_generate"] = c1 != c0
    page.screenshot(path=f"{SHOTS}/{LABEL}_02_generated.png", full_page=True)

    # Select BFS and run the self-chaining async handler
    sel = page.get_by_role("combobox").first
    r["select_found"] = sel.count() > 0
    sel.click()
    page.wait_for_timeout(700)
    page.get_by_role("option", name="BFS").click()
    page.wait_for_timeout(700)
    r["selected_text"] = sel.inner_text()
    page.get_by_role("button", name="Run", exact=True).click()
    # the handler re-chains itself every 10ms until done; give it time
    page.wait_for_timeout(9000)
    c2 = grid_colors(page)
    r["yellow_cells_after_bfs"] = sum(1 for c in c2 if "255, 255, 0" in c or "yellow" in c)
    r["bfs_painted"] = c2 != c1
    body = page.inner_text("body")
    r["toast_seen"] = ("Path found" in body) or ("No path found" in body)
    r["toast_text"] = next(
        (ln for ln in body.splitlines() if "Path" in ln and "found" in ln), None
    )
    page.screenshot(path=f"{SHOTS}/{LABEL}_03_bfs_done.png", full_page=True)

    # Clear resets the grid
    page.get_by_role("button", name="Clear").click()
    page.wait_for_timeout(1500)
    c3 = grid_colors(page)
    r["cleared_back_to_generated"] = c3 == c1
    page.screenshot(path=f"{SHOTS}/{LABEL}_04_cleared.png", full_page=True)

    # DFS run too
    sel.click()
    page.wait_for_timeout(700)
    page.get_by_role("option", name="DFS").click()
    page.wait_for_timeout(700)
    page.get_by_role("button", name="Run", exact=True).click()
    page.wait_for_timeout(9000)
    c4 = grid_colors(page)
    r["dfs_painted"] = c4 != c3
    body2 = page.inner_text("body")
    r["dfs_toast_seen"] = ("Path found" in body2) or ("No path found" in body2)
    page.screenshot(path=f"{SHOTS}/{LABEL}_05_dfs_done.png", full_page=True)

    # reload -> state survives the session, no hydration errors
    page.reload(wait_until="networkidle", timeout=60_000)
    page.wait_for_timeout(2500)
    r["grid_cells_after_reload"] = len(grid_colors(page))
    page.screenshot(path=f"{SHOTS}/{LABEL}_06_reload.png", full_page=True)

    browser.close()

print(json.dumps({
    "label": LABEL, "results": r,
    "console_errors": [c for c in console if c["type"] == "error"],
    "console_warnings": [c for c in console if c["type"] == "warning"],
    "page_errors": page_errors, "failed_requests": failed,
    "bad_responses": sorted(set(bad)),
}, indent=2, default=str))
