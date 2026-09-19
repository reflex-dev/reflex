"""Playwright driver for the reflex-enterprise ag_grid demo (reflex 0.9.11a1 campaign).

Usage: python drive_aggrid.py <base_url> <shots_dir> [route ...]

Visits each demo route, waits for the grid, performs per-route interactions
(sort, filter, edit, tab switch, selection, expand, scroll, chart), screenshots,
and records console messages, page errors and failed responses.
Writes <shots_dir>/report.json.
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
    "[vite] hot updated",
)
# AG Grid Enterprise trial/license banner is expected without a license key.
LICENSE_NOISE = ("License Key Not Found", "AG Grid Enterprise", "ag-grid-enterprise", "****")

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


def wait_grid(page, timeout=25000):
    page.wait_for_selector(".ag-root", timeout=timeout)
    try:
        page.wait_for_selector(".ag-cell, .ag-header-cell", timeout=timeout)
    except Exception:
        pass


def nrows(page):
    return page.locator(".ag-center-cols-container .ag-row").count()


def shot(page, name):
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=False)


def interact(page, route, entry):
    acts = entry["actions"]

    def note(msg):
        acts.append(str(msg))

    if route == "/":
        note(f"index links={page.locator('a[href]').count()}")
        titles = [t.inner_text() for t in page.locator("a[href^='/']").all()[:6]]
        note(f"card_titles={titles}")
        return

    wait_grid(page)
    note(f"initial rows={nrows(page)}")
    hdrs = [h.inner_text() for h in page.locator(".ag-header-cell-text").all()]
    note(f"headers={hdrs}")

    if route == "/editable":
        cell = page.locator(".ag-cell[col-id='name']").first
        before = cell.inner_text()
        cell.dblclick()
        page.keyboard.press("Control+a")
        page.keyboard.type("EditedByQA")
        page.keyboard.press("Enter")
        page.wait_for_timeout(1500)
        toast = page.locator("[data-sonner-toast], li[data-sonner-toast]")
        note(f"edit '{before}' -> '{page.locator('.ag-cell[col-id=name]').first.inner_text()}' toast_count={toast.count()}")
        if toast.count():
            note(f"toast_text={toast.first.inner_text()[:120]!r}")
        shot(page, "editable_after_edit")
    elif route == "/formatters":
        # check the python-callable renderer/formatter columns actually rendered
        def snapshot(tag):
            cells = {}
            for col in ("flag", "number", "currency number", "scaled number", "row counter"):
                loc = page.locator(f'.ag-cell[col-id="{col}"]').first
                cells[col] = loc.inner_text()[:40] if loc.count() else "<missing>"
            note(f"{tag} cells={cells}")
            return cells

        snapshot("inline")
        shot(page, "formatters_inline")
        btns = page.locator(".ag-cell button")
        note(f"inline memo-renderer buttons={btns.count()}")
        if btns.count():
            t0 = btns.first.inner_text()
            btns.first.click()
            page.wait_for_timeout(1200)
            note(f"row-counter button {t0!r} -> {btns.first.inner_text()!r}")
            btns.first.click()
            page.wait_for_timeout(1200)
            note(f"row-counter button 2nd click -> {btns.first.inner_text()!r}")
        # raw-data dialog (rxe.static registered component)
        raw = page.get_by_role("button", name="Raw Data")
        if raw.count():
            raw.first.click()
            page.wait_for_timeout(1000)
            dlg = page.locator("div[role='dialog']")
            note(f"raw-data dialog open={dlg.count()} text={dlg.first.inner_text()[:120]!r}" if dlg.count() else "raw-data dialog MISSING")
            shot(page, "formatters_rawdialog")
            page.keyboard.press("Escape")
            page.wait_for_timeout(600)
        for tab in ("State", "API", "Inline"):
            t = page.get_by_role("tab", name=tab, exact=True)
            if t.count():
                t.first.click()
                page.wait_for_timeout(1800)
                if tab == "API":
                    b = page.get_by_role("button", name="Set column defs")
                    if b.count():
                        b.first.click()
                        page.wait_for_timeout(1800)
                        note("clicked 'Set column defs'")
                note(f"tab={tab} rows={nrows(page)}")
                snapshot(f"tab:{tab}")
                shot(page, f"formatters_tab_{tab.lower()}")
    elif route == "/state-grid":
        for label in ("Load columns", "Load data", "Set Columns", "Set Data"):
            btn = page.get_by_role("button", name=label)
            if btn.count():
                btn.first.click()
                page.wait_for_timeout(1200)
                note(f"clicked '{label}' rows={nrows(page)}")
        note(f"rows_after_load={nrows(page)}")
    elif route in ("/model", "/model-auth", "/model-ssrm"):
        page.wait_for_timeout(3000)
        note(f"rows_after_wait={nrows(page)}")
        cells = [c.inner_text()[:20] for c in page.locator(".ag-cell").all()[:6]]
        note(f"first_cells={cells}")
        body = page.locator(".ag-body-viewport").first
        if body.count():
            body.evaluate("el => el.scrollTo(0, 3000)")
            page.wait_for_timeout(2500)
            note(f"rows_after_scroll={nrows(page)} first_cells={[c.inner_text()[:20] for c in page.locator('.ag-cell').all()[:4]]}")
        shot(page, slug(route) + "_scrolled")
    elif route == "/selected-items":
        boxes = page.locator(".ag-selection-checkbox input, .ag-checkbox-input")
        note(f"checkboxes={boxes.count()}")
        for i in (0, 1):
            if boxes.count() > i:
                boxes.nth(i).click()
                page.wait_for_timeout(800)
        body_text = page.locator("body").inner_text()
        note(f"selection_echo={' | '.join(l for l in body_text.splitlines() if 'select' in l.lower())[:200]}")
        shot(page, "selected_items_after")
    elif route == "/master-detail":
        exp = page.locator(".ag-group-contracted").first
        if exp.count():
            exp.click()
            page.wait_for_timeout(1800)
            note(f"expanded master detail_rows={page.locator('.ag-details-row').count()}")
            shot(page, "master_detail_expanded")
    elif route == "/tree":
        grp = page.locator(".ag-group-contracted").first
        if grp.count():
            grp.click()
            page.wait_for_timeout(1200)
            note(f"expanded tree rows_now={nrows(page)}")
            shot(page, "tree_expanded")
    elif route == "/pivot":
        note(f"pivot panel present={page.locator('.ag-column-drop, .ag-side-bar').count()}")
        sb = page.locator(".ag-side-button-button").first
        if sb.count():
            sb.click()
            page.wait_for_timeout(1200)
            note("opened sidebar tool panel")
            shot(page, "pivot_sidebar")
    elif route == "/integrated-charts":
        note(f"chart containers={page.locator('.ag-chart, .ag-chart-wrapper').count()}")
        shot(page, "integrated_charts_view")
    elif route in ("/simple-serialization", "/advanced-serialization"):
        for label in ("Save", "Restore", "Save State", "Restore State", "Get State", "Apply State"):
            b = page.get_by_role("button", name=label)
            if b.count():
                b.first.click()
                page.wait_for_timeout(1200)
                note(f"clicked '{label}'")
        txt = page.locator("body").inner_text()
        note(f"state_text_len={len(txt)}")
        shot(page, slug(route) + "_after_buttons")
    elif route == "/cell-selection":
        cells = page.locator(".ag-cell")
        if cells.count() > 3:
            cells.nth(0).click()
            page.mouse.down()
            box = cells.nth(3).bounding_box()
            if box:
                page.mouse.move(box["x"] + 5, box["y"] + 5)
            page.mouse.up()
            page.wait_for_timeout(1000)
            note(f"range_selected_cells={page.locator('.ag-cell-range-selected').count()}")
            note(f"echo={' | '.join(l for l in page.locator('body').inner_text().splitlines() if 'ell' in l)[:200]}")
        shot(page, "cell_selection_range")
    elif route == "/fill-handle":
        cells = page.locator(".ag-cell")
        if cells.count() > 1:
            cells.nth(0).click()
            page.wait_for_timeout(500)
            fh = page.locator(".ag-fill-handle")
            note(f"fill_handle_present={fh.count()}")
            if fh.count():
                b0 = fh.first.bounding_box()
                target = cells.nth(min(4, cells.count() - 1)).bounding_box()
                if b0 and target:
                    page.mouse.move(b0["x"] + 2, b0["y"] + 2)
                    page.mouse.down()
                    page.mouse.move(target["x"] + 5, target["y"] + 5, steps=8)
                    page.mouse.up()
                    page.wait_for_timeout(1200)
                    note("dragged fill handle")
        shot(page, "fill_handle_after")
    elif route == "/aligned-grids":
        note(f"grid_roots={page.locator('.ag-root').count()}")
        # scroll first grid horizontally, both should follow
        vp = page.locator(".ag-body-horizontal-scroll-viewport").first
        if vp.count():
            vp.evaluate("el => el.scrollTo(300, 0)")
            page.wait_for_timeout(1000)
            offs = page.eval_on_selector_all(
                ".ag-body-horizontal-scroll-viewport", "els => els.map(e => e.scrollLeft)"
            )
            note(f"h_scroll_offsets={offs}")
        shot(page, "aligned_grids_scrolled")

    # generic sort on the first header
    hdr = page.locator(".ag-header-cell-label").first
    if hdr.count():
        try:
            before = page.locator(".ag-cell").first.inner_text()[:30]
            hdr.click(timeout=4000)
            page.wait_for_timeout(900)
            after = page.locator(".ag-cell").first.inner_text()[:30]
            note(f"sort click: first_cell {before!r} -> {after!r}")
        except Exception as e:
            note(f"header sort skipped: {type(e).__name__}")
    # generic filter via the floating filter if present
    ff = page.locator(".ag-floating-filter-input input").first
    if ff.count():
        try:
            ff.fill("a")
            page.wait_for_timeout(1200)
            note(f"floating filter 'a' -> rows={nrows(page)}")
            ff.fill("")
            page.wait_for_timeout(800)
        except Exception as e:
            note(f"filter skipped: {type(e).__name__}")


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(viewport={"width": 1500, "height": 1000})
    page = ctx.new_page()

    console_msgs, page_errors, failed_resp = [], [], []
    page.on("console", lambda m: console_msgs.append({"type": m.type, "text": m.text[:400]}))
    page.on("pageerror", lambda e: page_errors.append(str(e)[:800]))
    page.on(
        "response",
        lambda r: failed_resp.append({"url": r.url[:220], "status": r.status})
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
            page.goto(BASE + route, wait_until="load", timeout=60000)
            page.wait_for_timeout(2500)
            interact(page, route, entry)
            entry["status"] = "ok"
        except Exception as e:
            entry["status"] = f"ERROR: {type(e).__name__}: {e}"[:500]
        entry["elapsed_s"] = round(time.time() - t0, 1)
        shot(page, slug(route))
        msgs = [
            m
            for m in console_msgs
            if not any(b in m["text"] for b in BENIGN_CONSOLE)
        ]
        entry["console_license_noise"] = sum(
            1 for m in msgs if any(n in m["text"] for n in LICENSE_NOISE)
        )
        entry["console"] = [
            m for m in msgs if not any(n in m["text"] for n in LICENSE_NOISE)
        ][:40]
        entry["pageerrors"] = list(page_errors)[:20]
        entry["failed"] = failed_resp[:30]
        print(
            f"{route:26s} {entry['status'][:40]:42s} {entry['elapsed_s']:6.1f}s "
            f"console={len(entry['console'])} lic={entry['console_license_noise']} "
            f"errs={len(entry['pageerrors'])} failed={len(entry['failed'])}"
        )

    ctx.close()
    browser.close()

(SHOTS / "report.json").write_text(json.dumps(report, indent=2))
print("\nwrote", SHOTS / "report.json")
