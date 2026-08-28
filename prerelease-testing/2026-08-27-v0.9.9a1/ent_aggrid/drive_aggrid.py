"""Playwright driver for the reflex-enterprise ag_grid demo.

Usage: python drive_aggrid.py <base_url> <shots_dir> [route ...]

Visits each demo route, waits for the grid to render, performs per-route
interactions (sort, filter, edit, scroll, tab switches), captures screenshots,
browser console messages, page errors, and failed network responses.
Writes a JSON report to <shots_dir>/report.json.
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
SHOTS = Path(sys.argv[2])
SHOTS.mkdir(parents=True, exist_ok=True)
ONLY = set(sys.argv[3:])

BENIGN_CONSOLE = (
    "HydrateFallback",
    "[vite] connecting",
    "[vite] connected",
    "React DevTools",
    "Download the React DevTools",
)

ALL_ROUTES = [
    "/",
    "/aligned-grids",
    "/cell-selection",
    "/editable",
    "/fill-handle",
    "/formatters",
    "/simple-serialization",
    "/advanced-serialization",
    "/integrated-charts",
    "/master-detail",
    "/model",
    "/model-auth",
    "/model-ssrm",
    "/pivot",
    "/selected-items",
    "/state-grid",
    "/tree",
]

report = {}


def slug(route):
    return route.strip("/").replace("/", "_") or "index"


def wait_grid(page, timeout=20000):
    """Wait for an AG Grid root and at least one row/cell to appear."""
    page.wait_for_selector(".ag-root", timeout=timeout)
    try:
        page.wait_for_selector(".ag-cell, .ag-header-cell", timeout=timeout)
    except Exception:
        pass


def interact(page, route, entry):
    """Route-specific interactions; append notes to entry['actions']."""
    acts = entry["actions"]

    def note(msg):
        acts.append(msg)

    if route == "/":
        cards = page.locator("a[href]")
        note(f"index links={cards.count()}")
        return

    wait_grid(page)
    rows = page.locator(".ag-center-cols-container .ag-row").count()
    note(f"initial rows={rows}")

    if route == "/editable":
        # double-click first name cell, type new value, Enter; expect toast
        cell = page.locator(".ag-cell[col-id='name']").first
        cell.dblclick()
        page.keyboard.press("Control+a")
        page.keyboard.type("Edited")
        page.keyboard.press("Enter")
        page.wait_for_timeout(1200)
        toast = page.locator("[data-sonner-toast], .Toastify__toast, li[data-sonner-toast]")
        note(f"edit done toast_count={toast.count()}")
        note(f"first_name_cell={page.locator('.ag-cell[col-id=name]').first.inner_text()}")
    elif route in ("/state-grid",):
        # buttons: load columns / load data etc.
        for label in ("Load columns", "Load data"):
            btn = page.get_by_role("button", name=label)
            if btn.count():
                btn.first.click()
                page.wait_for_timeout(800)
                note(f"clicked '{label}'")
        page.wait_for_timeout(1500)
        note(f"rows_after_load={page.locator('.ag-center-cols-container .ag-row').count()}")
    elif route in ("/model", "/model-auth", "/model-ssrm"):
        page.wait_for_timeout(2500)
        note(f"rows_after_wait={page.locator('.ag-center-cols-container .ag-row').count()}")
        # infinite scroll: scroll the grid body down
        body = page.locator(".ag-body-viewport").first
        if body.count():
            body.evaluate("el => el.scrollTo(0, 3000)")
            page.wait_for_timeout(2000)
            note("scrolled body to 3000")
            note(f"rows_after_scroll={page.locator('.ag-center-cols-container .ag-row').count()}")
    elif route == "/formatters":
        # switch tabs: inline (default), state, api
        for tab in ("State", "API", "Inline"):
            t = page.get_by_role("tab", name=tab)
            if t.count():
                t.first.click()
                page.wait_for_timeout(1000)
                note(f"tab '{tab}' clicked")
        # row counter button click (memo component in cell renderer)
        btns = page.locator(".ag-cell button")
        if btns.count():
            btns.first.click()
            page.wait_for_timeout(800)
            note(f"clicked in-grid button, now={btns.first.inner_text()!r}")
    elif route == "/selected-items":
        boxes = page.locator(".ag-selection-checkbox input, .ag-checkbox-input")
        n = boxes.count()
        if n:
            boxes.nth(0).click()
            page.wait_for_timeout(600)
            note("clicked first selection checkbox")
    elif route == "/master-detail":
        exp = page.locator(".ag-group-contracted .ag-icon").first
        if exp.count():
            exp.click()
            page.wait_for_timeout(1200)
            note(f"expanded master row detail_rows={page.locator('.ag-details-row').count()}")
    elif route == "/tree":
        grp = page.locator(".ag-group-contracted").first
        if grp.count():
            grp.click()
            page.wait_for_timeout(800)
            note("expanded tree group")

    # generic: sort by clicking the first header, then filter via header menu skip
    hdr = page.locator(".ag-header-cell-label").first
    if hdr.count():
        try:
            hdr.click(timeout=3000)
            page.wait_for_timeout(700)
            note("clicked header (sort)")
            first_cell = page.locator(".ag-cell").first
            if first_cell.count():
                note(f"first_cell_after_sort={first_cell.inner_text()[:40]!r}")
        except Exception as e:
            note(f"header sort skipped: {type(e).__name__}")


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(viewport={"width": 1400, "height": 950})
    page = ctx.new_page()

    console_msgs = []
    page_errors = []
    failed_resp = []
    page.on(
        "console",
        lambda m: console_msgs.append({"type": m.type, "text": m.text[:500]}),
    )
    page.on("pageerror", lambda e: page_errors.append(str(e)[:800]))
    page.on(
        "response",
        lambda r: failed_resp.append({"url": r.url[:200], "status": r.status})
        if r.status >= 400
        else None,
    )

    routes = [r for r in ALL_ROUTES if not ONLY or r in ONLY or slug(r) in ONLY]
    for route in routes:
        entry = {"actions": [], "console": [], "pageerrors": [], "failed": []}
        report[route] = entry
        console_msgs.clear()
        page_errors.clear()
        failed_resp.clear()
        t0 = time.time()
        try:
            page.goto(BASE + route, wait_until="load", timeout=45000)
            page.wait_for_timeout(2500)
            interact(page, route, entry)
            entry["status"] = "ok"
        except Exception as e:
            entry["status"] = f"ERROR: {type(e).__name__}: {e}"[:500]
        entry["elapsed_s"] = round(time.time() - t0, 1)
        page.screenshot(path=str(SHOTS / f"{slug(route)}.png"), full_page=False)
        entry["console"] = [
            m
            for m in console_msgs
            if not any(b in m["text"] for b in BENIGN_CONSOLE)
            and m["type"] in ("error", "warning")
        ]
        entry["all_console_count"] = len(console_msgs)
        entry["pageerrors"] = list(page_errors)
        entry["failed"] = list(failed_resp)
        print(
            f"{route}: {entry['status']} actions={entry['actions']} "
            f"console_err/warn={len(entry['console'])} pageerrors={len(page_errors)} "
            f"failed_req={len(failed_resp)}"
        )

    browser.close()

(SHOTS / "report.json").write_text(json.dumps(report, indent=2))
print("report written to", SHOTS / "report.json")
