"""Infinite-row ModelWrapper probe: text filter request/response vs rendered rows, and block paging by scrolling.

Usage: probe_infinite.py <base_url> <route> <sqlite_db> <out_json>
"""
import json
import sqlite3
import sys
import time
import urllib.parse

from playwright.sync_api import sync_playwright

base, route, dbpath, out = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3], sys.argv[4]
res, resp_log = {}, []


def db(q, *a):
    c = sqlite3.connect(dbpath)
    try:
        return c.execute(q, a).fetchall()
    finally:
        c.close()


def on_response(r):
    if "abstract-wrapper-data" not in r.url:
        return
    q = urllib.parse.parse_qs(urllib.parse.urlparse(r.url).query)
    try:
        body = r.json()
    except Exception:  # noqa: BLE001
        body = None
    n = None
    if isinstance(body, dict):
        rows = body.get("rows") or body.get("rowData") or body.get("data")
        n = len(rows) if isinstance(rows, list) else None
        keys = sorted(body)
    else:
        keys = type(body).__name__
        n = len(body) if isinstance(body, list) else None
    resp_log.append({"status": r.status, "startRow": q.get("startRow", [""])[0], "endRow": q.get("endRow", [""])[0],
                     "filterModel": q.get("filterModel", [""])[0], "n_rows": n, "keys": keys,
                     "lastRow": body.get("rowCount", body.get("lastRow")) if isinstance(body, dict) else None})


def names(p):
    return p.evaluate("""() => [...document.querySelectorAll('.ag-row[row-index]')]
      .map(r => ({i: +r.getAttribute('row-index'), n: ((r.querySelector('.ag-cell[col-id="name"]')||{}).innerText||'').trim()}))
      .sort((a,b)=>a.i-b.i)""")


with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    p = b.new_context().new_page()
    p.on("response", on_response)
    p.goto(base + route, wait_until="networkidle")
    p.wait_for_selector('.ag-row .ag-cell[col-id="name"]', timeout=60000)
    time.sleep(2)
    res["db_count"] = db("select count(*) from friend")[0][0]
    res["initial_rows"] = len(names(p))
    # paging: scroll the grid body to the bottom a few times
    for _ in range(4):
        res.setdefault("scrolled", []).append(p.evaluate("""() => { const c = [...document.querySelectorAll('.ag-body-viewport, .ag-body-vertical-scroll-viewport, .ag-grid-scrolling-container, .ag-center-cols-viewport')].filter(e => e.scrollHeight > e.clientHeight + 5); c.forEach(e => e.scrollTop = e.scrollHeight); return c.map(e => e.className.split(' ')[0]); }"""))
        time.sleep(1.5)
    rows = names(p)
    res["after_scroll"] = {"max_row_index": max((r["i"] for r in rows), default=-1), "n_rendered": len(rows),
                           "requests": [(x["startRow"], x["endRow"], x["status"], x["n_rows"], x["lastRow"]) for x in resp_log]}
    p.evaluate("""() => document.querySelectorAll('.ag-body-viewport, .ag-body-vertical-scroll-viewport, .ag-grid-scrolling-container, .ag-center-cols-viewport').forEach(e => e.scrollTop = 0)""")
    time.sleep(1.5)
    # text filter through the column menu filter (same UI path as drive_ag_model.text_filter)
    target = db("select name from friend order by id desc limit 1")[0][0]
    sub = target.split()[-1][:4]
    n0 = len(resp_log)
    p.click('.ag-header-cell[col-id="name"] .ag-header-cell-filter-button')
    p.wait_for_selector(".ag-filter", timeout=5000)
    p.locator(".ag-filter input.ag-input-field-input:not([type=checkbox]):visible").first.fill(sub)
    time.sleep(3)
    p.keyboard.press("Escape")
    time.sleep(1)
    rows = names(p)
    res["filter"] = {"sub": sub, "db_matches": db("select count(*) from friend where lower(name) like ?", f"%{sub.lower()}%")[0][0],
                     "requests_after_filter": resp_log[n0:], "rendered_nonempty": [r["n"] for r in rows if r["n"]][:10],
                     "rendered_total": len(rows)}
    p.screenshot(path=out.replace(".json", ".png"))
    b.close()
res["responses_all"] = resp_log
open(out, "w").write(json.dumps(res, indent=1))
print(json.dumps({k: v for k, v in res.items() if k != "responses_all"}, indent=1))
