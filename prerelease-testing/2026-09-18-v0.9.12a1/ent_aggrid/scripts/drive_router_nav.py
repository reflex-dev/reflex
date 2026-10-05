"""Exercise the router split (#7068) through the ag_grid demo's own nav Select.

The demo's header Select binds value=State.router.page.path and on_change=rx.redirect,
so it is a direct end-to-end probe of the per-field router vars after the 0.9.12
router split. Also records the websocket frames so the delta size / contents of a
client-side navigation can be inspected.

Usage: python drive_router_nav.py <base_url> <out_dir>
"""
import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
res = {"console": [], "pageerrors": [], "failed": [], "ws_in": [], "ws_out": []}

def sel_text(page):
    t = page.locator("button[role='combobox'], .rt-SelectTrigger").first
    return t.inner_text() if t.count() else "<no select>"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": 1500, "height": 1000})
    page = ctx.new_page()
    page.on("console", lambda m: res["console"].append(f"{m.type}: {m.text[:200]}"))
    page.on("pageerror", lambda e: res["pageerrors"].append(str(e)[:300]))
    page.on("requestfailed", lambda r: res["failed"].append(r.url[:200]))
    page.on("response", lambda r: res["failed"].append(f"{r.status} {r.url[:160]}") if r.status >= 400 else None)
    def _ws(ws):
        ws.on("framereceived", lambda pl: res["ws_in"].append((len(pl), str(pl)[:600])))
        ws.on("framesent", lambda pl: res["ws_out"].append((len(pl), str(pl)[:400])))
    page.on("websocket", _ws)

    # 1. direct load of a deep route: does the select reflect router.page.path?
    page.goto(BASE + "/tree", wait_until="load", timeout=60000)
    page.wait_for_selector(".ag-root", timeout=40000); page.wait_for_timeout(2500)
    res["direct_load_tree_select"] = sel_text(page)
    res["direct_load_tree_url"] = page.url

    # 2. client-side nav via the Select -> /pivot
    ws_in_before = len(res["ws_in"])
    page.locator("button[role='combobox'], .rt-SelectTrigger").first.click()
    page.wait_for_timeout(600)
    opt = page.get_by_role("option", name="Pivot", exact=False)
    if not opt.count():
        opt = page.locator("[role='option']").filter(has_text="Pivot")
    opt.first.click()
    page.wait_for_timeout(3000)
    res["after_select_nav_url"] = page.url
    res["after_select_nav_select"] = sel_text(page)
    res["ws_frames_during_nav"] = res["ws_in"][ws_in_before:]

    # 3. client-side nav back to index via the "AgGrid demo" heading link, then into /formatters
    page.goto(BASE + "/", wait_until="load", timeout=60000); page.wait_for_timeout(1500)
    link = page.get_by_role("link", name="Formatters", exact=False)
    if link.count():
        link.first.click()
        page.wait_for_selector(".ag-root", timeout=40000); page.wait_for_timeout(3000)
    res["clientside_to_formatters_url"] = page.url
    res["clientside_to_formatters_select"] = sel_text(page)
    btn = page.locator(".ag-cell button")
    res["formatters_memo_button_after_clientside_nav"] = btn.first.inner_text() if btn.count() else "<none>"
    if btn.count():
        btn.first.click(); page.wait_for_timeout(1200)
        res["formatters_memo_button_after_click"] = btn.first.inner_text()
    page.screenshot(path=str(OUT / "router_nav_formatters.png"))

    # 4. browser back/forward
    page.go_back(wait_until="load"); page.wait_for_timeout(2500)
    res["after_back_url"] = page.url
    res["after_back_select"] = sel_text(page)
    page.go_forward(wait_until="load"); page.wait_for_timeout(2500)
    res["after_forward_url"] = page.url
    res["after_forward_select"] = sel_text(page)
    page.screenshot(path=str(OUT / "router_nav_forward.png"))
    ctx.close(); b.close()

res["console"] = [c for c in res["console"] if "HydrateFallback" not in c and "vite]" not in c and "DevTools" not in c and "ag-grid.com" not in c and "*****" not in c and "License" not in c and "AG Grid Enterprise" not in c]
print(json.dumps(res, indent=2)[:4000])
(OUT / "router_nav_report.json").write_text(json.dumps(res, indent=2))
