"""Focused check: does row selection in ag_grid_finance fire on_selection_changed
and render the recharts line chart? Also inspects the grid's selection config."""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/"); SHOTS = Path(sys.argv[2]); SHOTS.mkdir(parents=True, exist_ok=True)
out = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 1500, "height": 1050}); page = ctx.new_page()
    msgs = []; page.on("console", lambda m: msgs.append(f"{m.type}: {m.text[:300]}"))
    page.goto(BASE + "/", wait_until="load", timeout=60000)
    page.wait_for_selector(".ag-root", timeout=40000); page.wait_for_timeout(2000)
    page.get_by_role("button", name="Fetch Latest Data").click(); page.wait_for_timeout(6000)

    out["checkbox_elems"] = page.locator(".ag-selection-checkbox").count()
    out["checkbox_inputs"] = page.locator(".ag-checkbox-input").count()
    out["ticker_cell_html"] = page.locator('.ag-cell[col-id="ticker"]').first.inner_html()[:300]

    # click the row body
    row = page.locator(".ag-center-cols-container .ag-row").first
    row.locator(".ag-cell").first.click()
    page.wait_for_timeout(4000)
    out["after_row_click_selected_rows"] = page.locator(".ag-row-selected").count()
    out["after_row_click_chart"] = page.locator(".recharts-wrapper, svg.recharts-surface").count()
    page.screenshot(path=str(SHOTS/"finsel_01_rowclick.png"), full_page=True)

    # ctrl-click / space
    page.keyboard.press("Space"); page.wait_for_timeout(3000)
    out["after_space_selected_rows"] = page.locator(".ag-row-selected").count()
    out["after_space_chart"] = page.locator(".recharts-wrapper, svg.recharts-surface").count()
    page.screenshot(path=str(SHOTS/"finsel_02_space.png"), full_page=True)

    out["headings"] = [h.inner_text()[:40] for h in page.locator("h1,h2,h3").all()]
    out["console"] = [m for m in msgs if "HydrateFallback" not in m and "[vite]" not in m]
    ctx.close(); b.close()
print(json.dumps(out, indent=2))
(SHOTS/"finance_selection_report.json").write_text(json.dumps(out, indent=2))
