"""Deeper interactions: integrated charts (range + context menu), fill handle drag,
aligned-grid horizontal sync, editable validation, and the demo 'Source' tab.

Usage: python drive_deep.py <base_url> <shots_dir>
"""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
SHOTS = Path(sys.argv[2]); SHOTS.mkdir(parents=True, exist_ok=True)
out = {}
BENIGN = ("HydrateFallback", "[vite] conn", "React DevTools", "Disconnect websocket")
LIC = ("License Key Not Found", "trial license key", "unlocked for trial", "AG Grid Enterprise", "***")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 1500, "height": 1000})
    page = ctx.new_page()
    msgs, errs, failed = [], [], []
    page.on("console", lambda m: msgs.append(f"{m.type}: {m.text[:250]}"))
    page.on("pageerror", lambda e: errs.append(str(e)[:400]))
    page.on("response", lambda r: failed.append(f"{r.status} {r.url[:150]}") if r.status >= 400 else None)

    def sec(name):
        msgs.clear(); errs.clear(); failed.clear()
        out[name] = {}
        return out[name]

    # ---------- integrated charts: range select + context menu chart ----------
    e = sec("integrated_charts")
    page.goto(BASE + "/integrated-charts", wait_until="load", timeout=60000)
    page.wait_for_selector(".ag-cell", timeout=30000); page.wait_for_timeout(2000)
    c0 = page.locator(".ag-cell").nth(0); c1 = page.locator(".ag-cell").nth(7)
    b0, b1 = c0.bounding_box(), c1.bounding_box()
    page.mouse.move(b0["x"]+5, b0["y"]+5); page.mouse.down()
    page.mouse.move(b1["x"]+5, b1["y"]+5, steps=6); page.mouse.up()
    page.wait_for_timeout(800)
    e["range_cells"] = page.locator(".ag-cell-range-selected").count()
    page.mouse.click(b1["x"]+5, b1["y"]+5, button="right")
    page.wait_for_timeout(1200)
    menu = page.locator(".ag-menu")
    e["context_menu_open"] = menu.count()
    e["menu_items"] = [t.inner_text()[:40] for t in page.locator(".ag-menu-option-text").all()][:15]
    page.screenshot(path=str(SHOTS/"charts_01_contextmenu.png"))
    chart_item = page.locator(".ag-menu-option-text", has_text="Chart")
    if chart_item.count():
        chart_item.first.hover(); page.wait_for_timeout(1200)
        page.screenshot(path=str(SHOTS/"charts_02_submenu.png"))
        sub = page.locator(".ag-menu-option-text", has_text="Column")
        if sub.count():
            sub.first.hover(); page.wait_for_timeout(900)
            leaf = page.locator(".ag-chart-settings-mini-wrapper, .ag-menu-option").filter(has_text="Grouped").first
            try:
                leaf.click(timeout=4000)
            except Exception:
                pass
            page.wait_for_timeout(2500)
    e["chart_wrappers"] = page.locator(".ag-chart, .ag-chart-wrapper, canvas").count()
    page.screenshot(path=str(SHOTS/"charts_03_after_chart.png"))
    e["console"] = [m for m in msgs if not any(x in m for x in BENIGN) and not any(x in m for x in LIC)]
    e["license_noise"] = sum(1 for m in msgs if any(x in m for x in LIC))
    e["pageerrors"] = list(errs); e["failed"] = list(failed)

    # ---------- fill handle ----------
    e = sec("fill_handle")
    page.goto(BASE + "/fill-handle", wait_until="load", timeout=60000)
    page.wait_for_selector(".ag-cell", timeout=30000); page.wait_for_timeout(1800)
    gold = page.locator('.ag-cell[col-id="gold"]')
    e["gold_cells"] = gold.count()
    if gold.count() > 3:
        vals_before = [gold.nth(i).inner_text() for i in range(4)]
        gold.nth(0).click(); page.wait_for_timeout(700)
        fh = page.locator(".ag-fill-handle")
        e["fill_handle_present"] = fh.count()
        if fh.count():
            fb = fh.first.bounding_box(); tb = gold.nth(3).bounding_box()
            page.mouse.move(fb["x"]+3, fb["y"]+3); page.mouse.down()
            page.mouse.move(tb["x"]+10, tb["y"]+10, steps=10); page.mouse.up()
            page.wait_for_timeout(1500)
        vals_after = [gold.nth(i).inner_text() for i in range(4)]
        e["gold_before"] = vals_before; e["gold_after"] = vals_after
        e["fill_applied"] = vals_before != vals_after
    page.screenshot(path=str(SHOTS/"fillhandle_after_drag.png"))
    e["console"] = [m for m in msgs if not any(x in m for x in BENIGN) and not any(x in m for x in LIC)]
    e["pageerrors"] = list(errs); e["failed"] = list(failed)

    # ---------- aligned grids horizontal sync ----------
    e = sec("aligned_grids")
    page.goto(BASE + "/aligned-grids", wait_until="load", timeout=60000)
    page.wait_for_selector(".ag-cell", timeout=30000); page.wait_for_timeout(1800)
    e["roots"] = page.locator(".ag-root").count()
    before = page.eval_on_selector_all(".ag-body-viewport", "els => els.map(x => x.scrollLeft)")
    page.eval_on_selector_all(".ag-body-viewport", "els => { if (els[0]) els[0].scrollLeft = 250; }")
    page.wait_for_timeout(1200)
    after = page.eval_on_selector_all(".ag-body-viewport", "els => els.map(x => x.scrollLeft)")
    e["scrollLeft_before"] = before; e["scrollLeft_after"] = after
    e["synced"] = len(set(after)) == 1 and after and after[0] != 0
    page.screenshot(path=str(SHOTS/"aligned_after_hscroll.png"))
    e["console"] = [m for m in msgs if not any(x in m for x in BENIGN) and not any(x in m for x in LIC)]
    e["pageerrors"] = list(errs); e["failed"] = list(failed)

    # ---------- editable: invalid value + second edit + source tab ----------
    e = sec("editable_more")
    page.goto(BASE + "/editable", wait_until="load", timeout=60000)
    page.wait_for_selector(".ag-cell", timeout=30000); page.wait_for_timeout(1500)
    age = page.locator('.ag-cell[col-id="age"]').first
    age.dblclick(); page.keyboard.press("Control+a"); page.keyboard.type("999"); page.keyboard.press("Enter")
    page.wait_for_timeout(1500)
    e["age_after"] = page.locator('.ag-cell[col-id="age"]').first.inner_text()
    e["toasts"] = page.locator("[data-sonner-toast]").count()
    e["toast_texts"] = [t.inner_text()[:80] for t in page.locator("[data-sonner-toast]").all()]
    src = page.get_by_role("tab", name="Source")
    if src.count():
        src.first.click(); page.wait_for_timeout(1800)
        e["source_tab_code_len"] = len(page.locator("pre, code").first.inner_text()) if page.locator("pre, code").count() else 0
        page.screenshot(path=str(SHOTS/"editable_source_tab.png"))
    e["console"] = [m for m in msgs if not any(x in m for x in BENIGN) and not any(x in m for x in LIC)]
    e["pageerrors"] = list(errs); e["failed"] = list(failed)

    # ---------- selected-items: select all / deselect all ----------
    e = sec("selected_items_more")
    page.goto(BASE + "/selected-items", wait_until="load", timeout=60000)
    page.wait_for_selector(".ag-cell", timeout=30000); page.wait_for_timeout(1800)
    def panel_count():
        txt = page.locator("body").inner_text()
        for line in txt.splitlines():
            if line.startswith("Selected Items ("):
                return line
        return "?"
    e["initial_panel"] = panel_count()
    for label in ("Select All", "Deselect All"):
        btn = page.get_by_role("button", name=label)
        if btn.count():
            btn.first.click(); page.wait_for_timeout(1500)
            e[f"after_{label.replace(' ','_')}"] = panel_count()
    sel = page.get_by_role("button", name="Select by Direction")
    if sel.count():
        sel.first.click(); page.wait_for_timeout(1200)
        e["after_select_by_direction"] = panel_count()
    page.screenshot(path=str(SHOTS/"selected_items_more.png"))
    e["console"] = [m for m in msgs if not any(x in m for x in BENIGN) and not any(x in m for x in LIC)]
    e["pageerrors"] = list(errs); e["failed"] = list(failed)

    ctx.close(); b.close()

print(json.dumps(out, indent=2)[:6000])
(SHOTS/"deep_report.json").write_text(json.dumps(out, indent=2))
