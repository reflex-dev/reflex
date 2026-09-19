"""Playwright driver for the reflex-examples ag_grid_finance app.

Usage: python drive_finance.py <base_url> <shots_dir>

Exercises: initial render, "Fetch Latest Data" (state -> row_data), pagination
(page size selector + next page), column filter, sorting, row selection ->
recharts line chart, and the grid theme switcher (all four themes).
"""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
SHOTS = Path(sys.argv[2]); SHOTS.mkdir(parents=True, exist_ok=True)
BENIGN = ("HydrateFallback", "[vite] conn", "React DevTools", "Disconnect websocket")
out = {}

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 1500, "height": 1050})
    page = ctx.new_page()
    msgs, errs, failed = [], [], []
    page.on("console", lambda m: msgs.append(f"{m.type}: {m.text[:250]}"))
    page.on("pageerror", lambda e: errs.append(str(e)[:400]))
    page.on("response", lambda r: failed.append(f"{r.status} {r.url[:160]}") if r.status >= 400 else None)

    def rows():
        return page.locator(".ag-center-cols-container .ag-row").count()

    page.goto(BASE + "/", wait_until="load", timeout=60000)
    page.wait_for_selector(".ag-root", timeout=40000)
    page.wait_for_timeout(2500)
    out["initial_rows"] = rows()
    out["headers"] = [h.inner_text() for h in page.locator(".ag-header-cell-text").all()]
    page.screenshot(path=str(SHOTS/"fin_01_initial.png"))

    # Fetch data
    page.get_by_role("button", name="Fetch Latest Data").click()
    page.wait_for_timeout(6000)
    out["rows_after_fetch"] = rows()
    out["first_row_cells"] = [c.inner_text() for c in page.locator(".ag-center-cols-container .ag-row").first.locator(".ag-cell").all()]
    page.screenshot(path=str(SHOTS/"fin_02_after_fetch.png"))

    # Pagination
    ps = page.locator(".ag-paging-panel")
    out["paging_panel"] = ps.inner_text().replace("\n", " ")[:160] if ps.count() else "<none>"
    nxt = page.locator("[data-ref='btNext'], .ag-paging-button[aria-label*='Next']").first
    if nxt.count():
        nxt.click(); page.wait_for_timeout(1500)
        out["paging_after_next"] = page.locator(".ag-paging-panel").inner_text().replace("\n"," ")[:160]
        out["rows_page2"] = rows()
        out["page2_first_cells"] = [c.inner_text() for c in page.locator(".ag-center-cols-container .ag-row").first.locator(".ag-cell").all()][:3]
    page.screenshot(path=str(SHOTS/"fin_03_page2.png"))
    # page size selector
    sel = page.locator(".ag-paging-page-size select, .ag-picker-field").first
    if sel.count():
        try:
            sel.click(); page.wait_for_timeout(800)
            opt = page.locator(".ag-list-item", has_text="50").first
            if opt.count():
                opt.click(); page.wait_for_timeout(1800)
                out["rows_after_pagesize_50"] = rows()
        except Exception as e:
            out["pagesize_err"] = f"{type(e).__name__}: {e}"[:150]
    page.screenshot(path=str(SHOTS/"fin_04_pagesize.png"))

    # Filter on ticker
    hdr = page.locator(".ag-header-cell", has_text="Ticker").first
    menu_btn = hdr.locator(".ag-header-cell-menu-button, .ag-icon-menu, .ag-icon-filter").first
    try:
        hdr.hover(); page.wait_for_timeout(400)
        menu_btn.click(timeout=4000); page.wait_for_timeout(1200)
        inp = page.locator(".ag-filter input, .ag-filter-body input").first
        if inp.count():
            inp.fill("AAPL"); page.wait_for_timeout(2000)
            out["rows_filter_AAPL"] = rows()
            out["filtered_tickers"] = sorted({c.inner_text() for c in page.locator('.ag-cell[col-id="ticker"]').all()})
            page.screenshot(path=str(SHOTS/"fin_05_filtered.png"))
            inp.fill(""); page.wait_for_timeout(1500)
        page.keyboard.press("Escape")
    except Exception as e:
        out["filter_err"] = f"{type(e).__name__}: {e}"[:200]

    # Sort by close
    ch = page.locator(".ag-header-cell-label", has_text="Close").first
    if ch.count():
        before = [c.inner_text() for c in page.locator('.ag-cell[col-id="close"]').all()][:3]
        ch.click(); page.wait_for_timeout(1500)
        after = [c.inner_text() for c in page.locator('.ag-cell[col-id="close"]').all()][:3]
        out["close_sort"] = {"before": before, "after": after, "changed": before != after}

    # Row selection -> chart
    cb = page.locator(".ag-selection-checkbox input, .ag-checkbox-input").first
    if cb.count():
        cb.click(); page.wait_for_timeout(4000)
    out["chart_svg"] = page.locator(".recharts-wrapper, svg.recharts-surface").count()
    out["heading_company"] = page.locator("h1, h2, h3").last.inner_text()[:40]
    out["error_bars"] = page.locator(".recharts-errorBar, .recharts-layer.recharts-error-bar").count()
    page.screenshot(path=str(SHOTS/"fin_06_selection_chart.png"), full_page=True)

    # Theme switch
    themes_seen = {}
    for theme in ("balham", "alpine", "material", "quartz"):
        try:
            trg = page.locator("button.rt-SelectTrigger, [role='combobox']").first
            trg.click(); page.wait_for_timeout(700)
            page.get_by_role("option", name=theme).click()
            page.wait_for_timeout(2200)
            cls = page.locator(".ag-root-wrapper").first.get_attribute("class") or ""
            themes_seen[theme] = [c for c in cls.split() if "theme" in c or "ag-" in c][:6]
            page.screenshot(path=str(SHOTS/f"fin_07_theme_{theme}.png"))
        except Exception as e:
            themes_seen[theme] = f"ERR {type(e).__name__}: {e}"[:140]
    out["themes"] = themes_seen

    out["console"] = [m for m in msgs if not any(x in m for x in BENIGN)]
    out["pageerrors"] = errs
    out["failed"] = failed
    ctx.close(); b.close()

print(json.dumps(out, indent=2)[:7000])
(SHOTS/"finance_report.json").write_text(json.dumps(out, indent=2))
