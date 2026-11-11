"""Characterise AG Grids whose column_defs come from State vars (prod vs dev, per version).

Usage: probe_state_coldefs.py <base_url> <out_dir> <expected_venv> <label>
Reports, per grid, the rendered header texts and row count after a full page load,
after client-side navigation, and after a State change; plus whether window.__reflex
existed at load and whether the boot hydrate delivered the grid's state.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session, assert_driver_and_server  # noqa: E402

base, out, venv, label = sys.argv[1:5]
info = assert_driver_and_server(venv)
GRIDS = {"/master-detail": ["state-vars-grid", "static-objects-grid"], "/qa-grid-memo": ["qa_memo_grid", "qa_cs_a", "qa_cs_b"]}


def snap(p, gids):
    return {g: {"headers": [h for h in p.locator(f'[grid-id="{g}"] .ag-header-cell-text').all_inner_texts() if h.strip()],
                "rows": p.locator(f'[grid-id="{g}"] .ag-grid-scrolling-container .ag-row, [grid-id="{g}"] .ag-center-cols-container .ag-row').count()} for g in gids}


with Session(f"probe_state_coldefs-{label}", Path(out)) as s:
    s.note(f"guard: {info['versions']}")
    ctx = s.new_context("full-load")
    # Record whether window.__reflex exists when the first module scripts run / at DOMContentLoaded.
    ctx.add_init_script("document.addEventListener('DOMContentLoaded', () => { window.__qa_reflex_at_dcl = typeof window.__reflex; });")
    p = ctx.new_page()
    frames = []
    p.on("websocket", lambda ws: ws.on("framereceived", lambda f: frames.append(str(f)[:4000])))
    res = {}
    for route, gids in GRIDS.items():
        frames.clear()
        p.goto(base + route, wait_until="networkidle")
        p.wait_for_timeout(5000)
        res[f"{route} full load +5s"] = snap(p, gids)
        res[f"{route} __reflex at DOMContentLoaded"] = p.evaluate("() => window.__qa_reflex_at_dcl")
        res[f"{route} __reflex now"] = p.evaluate("() => typeof window.__reflex")
        key = "master_detail_state" if route == "/master-detail" else "qa_grid_state"
        res[f"{route} boot hydrate frames mentioning {key}"] = sum(1 for f in frames if key in f)
        res[f"{route} boot frames (event deltas) count"] = sum(1 for f in frames if '"delta"' in f)
        s.shot(p, route.strip("/") + "-full-load")
        for g in gids:
            hdr = res[f"{route} full load +5s"][g]["headers"]
            s.check(f"{route} [{g}] has columns after full load", bool(hdr), hdr)
    p.click("#qa-toggle-col")
    p.wait_for_timeout(2000)
    res["/qa-grid-memo after toggling State.fields"] = snap(p, GRIDS["/qa-grid-memo"])
    p.click("#qa_cs_a-add")
    p.wait_for_timeout(2000)
    res["/qa-grid-memo after CS-a add_row (row_data change only)"] = snap(p, GRIDS["/qa-grid-memo"])
    p.reload(wait_until="networkidle")
    p.wait_for_timeout(4000)
    res["/qa-grid-memo after reload"] = snap(p, GRIDS["/qa-grid-memo"])
    # client-side navigation: start at index and click the card link
    p.goto(base + "/", wait_until="networkidle")
    p.wait_for_timeout(2000)
    p.click("a:has-text('Master Detail')")
    p.wait_for_timeout(4000)
    res["/master-detail via client-side nav"] = snap(p, GRIDS["/master-detail"])
    s.check("/master-detail [state-vars-grid] has columns after client-side nav", bool(res["/master-detail via client-side nav"]["state-vars-grid"]["headers"]), res["/master-detail via client-side nav"])
    s.shot(p, "md-clientnav")
    # formatters page: State tab uses State-var column defs
    p.goto(base + "/formatters", wait_until="networkidle")
    p.wait_for_timeout(2500)
    tabs = p.locator("[role=tab]").all_inner_texts()
    res["/formatters tabs"] = tabs
    if p.locator("[role=tab]:has-text('State')").count():
        p.click("[role=tab]:has-text('State')")
        p.wait_for_timeout(2000)
        hdr = [h for h in p.locator(".ag-header-cell-text:visible").all_inner_texts() if h.strip()]
        res["/formatters State tab headers"] = hdr
        s.check("/formatters State tab (State-var column defs) has columns", bool(hdr), hdr)
        s.shot(p, "formatters-state-tab")
    for k, v in res.items():
        print(k, "=>", json.dumps(v))
    s.note(json.dumps(res))
