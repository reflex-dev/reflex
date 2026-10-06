"""Characterise grids whose column_defs/row_data are State-var defaults (prod vs dev).

Usage: probe_state_coldefs.py <base_url> <out_dir> <label>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session  # noqa: E402

base, out, label = sys.argv[1:4]
GRIDS = {"/master-detail": ["state-vars-grid", "static-objects-grid"], "/qa-grid-memo": ["qa_memo_grid", "qa_cs_a", "qa_cs_b"]}


def snap(p, gids):
    return {g: {"headers": [h for h in p.locator(f'[grid-id="{g}"] .ag-header-cell-text').all_inner_texts() if h.strip()],
                "rows": p.locator(f'[grid-id="{g}"] .ag-grid-scrolling-container .ag-row, [grid-id="{g}"] .ag-center-cols-container .ag-row').count()} for g in gids}


with Session(f"probe_state_coldefs-{label}", Path(out)) as s:
    p = s.new_page(label="full-load")
    res = {}
    for route, gids in GRIDS.items():
        p.goto(base + route, wait_until="networkidle")
        p.wait_for_timeout(5000)
        res[f"{route} full load +5s"] = snap(p, gids)
    p.click("#qa-toggle-col")
    p.wait_for_timeout(2000)
    res["/qa-grid-memo after toggling State.fields"] = snap(p, GRIDS["/qa-grid-memo"])
    p.click("#qa_cs_a-add")
    p.wait_for_timeout(2000)
    res["/qa-grid-memo after CS-a add_row"] = snap(p, GRIDS["/qa-grid-memo"])
    p.reload(wait_until="networkidle")
    p.wait_for_timeout(4000)
    res["/qa-grid-memo after reload"] = snap(p, GRIDS["/qa-grid-memo"])
    # client-side navigation: start at index and click the card link
    p.goto(base + "/", wait_until="networkidle")
    p.wait_for_timeout(2000)
    p.click("a:has-text('Master Detail')")
    p.wait_for_timeout(4000)
    res["/master-detail via client-side nav"] = snap(p, GRIDS["/master-detail"])
    s.shot(p, "md-clientnav")
    # what does the page JS see? dump initial state embedded in html for master detail state
    html = p.evaluate("async () => (await fetch('/master-detail')).text()")
    res["html_contains_master_data"] = "Product A" in html
    for k, v in res.items():
        print(k, "=>", json.dumps(v))
    s.note(json.dumps(res))
