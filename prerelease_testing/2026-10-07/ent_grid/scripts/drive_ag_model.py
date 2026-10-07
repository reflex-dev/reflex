"""Drive the AG Grid ModelWrapper demo pages against a real sqlite DB and verify DB effects.

Usage: drive_ag_model.py <base_url> <out_dir> <expected_venv> <sqlite_db_path> [pages]
pages: comma list of ssrm,workaround,simple,auth (default all)
"""

import json
import os
import re
import sqlite3
import sys
import traceback
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session, assert_driver_and_server  # noqa: E402

base, out, venv, dbpath = sys.argv[1:5]
pages = (sys.argv[5] if len(sys.argv) > 5 else "ssrm,workaround,simple,auth").split(",")
info = assert_driver_and_server(venv)


def db(q, *a):
    c = sqlite3.connect(dbpath)
    try:
        return c.execute(q, a).fetchall()
    finally:
        c.close()


def count():
    return db("select count(*) from friend")[0][0]


def data_reqs(s, since):
    return [r["url"] for r in s.requests[since:] if "/abstract-wrapper-data" in r["url"]]


def rows(page, col):
    return page.evaluate(
        """(col) => [...document.querySelectorAll('.ag-grid-scrolling-container .ag-row, .ag-center-cols-container .ag-row')]
        .map(r => ({idx: +r.getAttribute('row-index'), id: r.getAttribute('row-id'),
                    val: ((r.querySelector(`.ag-cell[col-id="${col}"]`) || {}).innerText || '').trim()}))
        .filter(r => !Number.isNaN(r.idx)).sort((a, b) => a.idx - b.idx)""",
        col,
    )


def cell_values(page, col):
    return [r["val"] for r in rows(page, col)]


def wait_rows(page, n_min=1, timeout=15000):
    page.wait_for_function(
        "(n) => document.querySelectorAll('.ag-grid-scrolling-container .ag-row .ag-cell[col-id=\"name\"], .ag-center-cols-container .ag-row .ag-cell[col-id=\"name\"]').length >= n"
        " && [...document.querySelectorAll('.ag-grid-scrolling-container .ag-row .ag-cell[col-id=\"name\"], .ag-center-cols-container .ag-row .ag-cell[col-id=\"name\"]')].some(c => c.innerText.trim() !== '')",
        arg=n_min,
        timeout=timeout,
    )
    page.wait_for_timeout(500)


def sort_by(page, col):
    page.click(f'.ag-header-cell[col-id="{col}"] .ag-header-cell-label')
    page.wait_for_timeout(2000)


def run_step(s, name, fn):
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        s.check(name, False, f"exception: {e!r}"[:600])
        traceback.print_exc()


def text_filter(page, col, value):
    page.click(f'.ag-header-cell[col-id="{col}"] .ag-header-cell-filter-button')
    page.wait_for_selector(".ag-filter", timeout=5000)
    inp = page.locator(".ag-filter input.ag-input-field-input:not([type=checkbox]):visible").first
    inp.fill(value)
    page.wait_for_timeout(2500)
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)


def edit_cell(page, row_id_col_value, col, new_value):
    """Double-click the `col` cell of the row whose id cell equals row_id_col_value and type."""
    row = page.locator(".ag-grid-scrolling-container .ag-row, .ag-center-cols-container .ag-row", has=page.locator(f'.ag-cell[col-id="id"]:text-is("{row_id_col_value}")')).first
    row.locator(f'.ag-cell[col-id="{col}"]').dblclick()
    page.wait_for_timeout(500)
    editor = page.locator(".ag-cell-inline-editing input, .ag-popup-editor input").first
    editor.fill(str(new_value))
    editor.press("Enter")
    page.wait_for_timeout(2500)


with Session(f"ag_model-{venv}", Path(out)) as s:
    s.note(f"guard: {info['versions']}")
    s.note(f"db rows at start: {count()}")

    if "ssrm" in pages:
        ctx = s.new_context("ssrm")
        p = ctx.new_page()

        resp_log = []

        def _on_resp(r):
            if "abstract-wrapper-data" in r.url:
                try:
                    t = r.text()
                    b = t[:100] + " ... " + t[-60:]
                except Exception as e:  # noqa: BLE001
                    b = repr(e)
                resp_log.append((s._ts(), r.status, b))

        p.on("response", _on_resp)

        def ssrm():
            i0 = len(s.requests)
            p.goto(base + "/model-ssrm", wait_until="networkidle")
            p.wait_for_timeout(1500)
            reqs = data_reqs(s, i0)
            s.check("ssrm: logged-out initial data request made", len(reqs) >= 1, reqs[:2])
            if reqs:
                q = urllib.parse.parse_qs(urllib.parse.urlparse(reqs[0]).query)
                s.check("ssrm: datasource URL carries endpoint_kwargs (state, sid) + SSRM params", {"state", "sid"} <= set(q) and any(k.lower().startswith("start") for k in q), {k: v[0][:80] for k, v in q.items()})
            s.check("ssrm: logged out shows no rows", len(rows(p, "name")) == 0, len(rows(p, "name")))
            p.click("button:has-text('Login')")
            p.wait_for_selector("button:has-text('Generate Friends')", timeout=10000)
            before = count()
            p.click("button:has-text('Generate Friends')")
            p.wait_for_selector("text=Created 50 friends.", timeout=15000)
            p.wait_for_timeout(1500)
            after = count()
            s.check("ssrm: Generate Friends inserted 50 rows into sqlite", after - before == 50, {"before": before, "after": after})
            p.wait_for_timeout(1500)
            s.note(f"ssrm rows right after generate (demo only calls setRowCount, no SSRM refresh): {len(rows(p, 'name'))}")
            p.reload(wait_until="networkidle")
            p.wait_for_selector("button:has-text('Logout')", timeout=10000)
            s.check("ssrm: login (backend var) survives reload", True, "Logout button shown after reload")
            try:
                wait_rows(p)
                s.check("ssrm: rows render on reload right after generate (row_count_cached interval=10s)", True, "")
            except Exception as e:  # noqa: BLE001
                s.check("ssrm: rows render on reload right after generate (row_count_cached interval=10s)", False, f"{e!r}"[:200])
                s.note(f"ssrm datasource responses so far: {resp_log}")
                s.shot(p, "ssrm-stale-rowcount")
                p.wait_for_timeout(11000)
                p.reload(wait_until="networkidle")
                wait_rows(p)
                s.check("ssrm: rows render on reload >10s after generate", True, "")
            s.shot(p, "ssrm-loaded")
            s.check("ssrm: rows rendered after generate", len(rows(p, "name")) > 0, len(rows(p, "name")))
            # sort by age asc / desc
            i1 = len(s.requests)
            sort_by(p, "age")
            ages = [int(v) for v in cell_values(p, "age") if v.isdigit()]
            reqs = data_reqs(s, i1)
            sm = [urllib.parse.parse_qs(urllib.parse.urlparse(u).query).get("sortModel", [""])[0] for u in reqs]
            dbmin = db("select min(age) from friend")[0][0]
            s.check("ssrm: sort asc request carries sortModel(age)", any("age" in x for x in sm), sm[:2])
            s.check("ssrm: sort asc first row has min age from db", bool(ages) and ages[0] == dbmin and ages == sorted(ages), {"first_rows": ages[:8], "db_min": dbmin})
            sort_by(p, "age")
            ages = [int(v) for v in cell_values(p, "age") if v.isdigit()]
            dbmax = db("select max(age) from friend")[0][0]
            s.check("ssrm: sort desc first row has max age", bool(ages) and ages[0] == dbmax and ages == sorted(ages, reverse=True), {"first_rows": ages[:8], "db_max": dbmax})
            sort_by(p, "age")  # clear sort
            # text filter on name
            some_name = db("select name from friend order by id limit 1")[0][0]
            sub = some_name.split()[0][:4]
            i2 = len(s.requests)
            text_filter(p, "name", sub)
            names = cell_values(p, "name")
            fm = [urllib.parse.parse_qs(urllib.parse.urlparse(u).query).get("filterModel", [""])[0] for u in data_reqs(s, i2)]
            exp = db("select count(*) from friend where lower(name) like ?", f"%{sub.lower()}%")[0][0]
            s.check("ssrm: filter request carries filterModel(name)", any("name" in x for x in fm), fm[-1:])
            s.check("ssrm: filtered rows all match and count matches db", bool(names) and all(sub.lower() in n.lower() for n in names) and len(names) == min(exp, 50), {"sub": sub, "shown": len(names), "blank_rows": sum(1 for n in names if not n), "db_matches": exp, "sample": names[:5]})
            s.shot(p, "ssrm-filtered")
            text_filter(p, "name", "")
            # edit a name cell
            wait_rows(p)
            first = rows(p, "id")[0]["val"]
            edit_cell(p, first, "name", "QA Edited SSRM")
            got = db("select name from friend where id=?", int(first))[0][0]
            s.check("ssrm: editing a cell updates sqlite", got == "QA Edited SSRM", {"id": first, "db_name": got})
            p.wait_for_timeout(1500)
            s.check("ssrm: edited value visible after refresh", "QA Edited SSRM" in cell_values(p, "name"), cell_values(p, "name")[:5])
            # multi-row selection -> selected_items computed var badges
            boxes = p.locator(".ag-row .ag-selection-checkbox input")
            n_boxes = boxes.count()
            if n_boxes >= 2:
                boxes.nth(0).click()
                boxes.nth(1).click()
                p.wait_for_timeout(1500)
                badges = p.locator(".rt-Badge").all_inner_texts()
                s.check("ssrm: selection -> selected_items computed var renders 2 badges", len([b for b in badges if b.strip()]) >= 2, badges[:6])
            else:
                s.check("ssrm: selection checkboxes present", False, n_boxes)
            # advanced filter toggle
            p.click(".rt-SwitchRoot")
            p.wait_for_timeout(2000)
            s.check("ssrm: enable_advanced_filter switch shows advanced filter bar", p.locator(".ag-advanced-filter").count() > 0, p.locator(".ag-advanced-filter").count())
            s.shot(p, "ssrm-advanced-filter")
            # logout -> no rows
            p.click("button:has-text('Logout')")
            p.wait_for_timeout(2500)
            s.check("ssrm: logout refreshes grid to empty", len(rows(p, "name")) == 0, len(rows(p, "name")))

        run_step(s, "ssrm flow", ssrm)
        s.shot(p, "ssrm-end")

    if "workaround" in pages:
        ctx = s.new_context("workaround")
        p = ctx.new_page()

        def workaround():
            i0 = len(s.requests)
            p.goto(base + os.environ.get("QA_INFINITE_ROUTE", "/qa-model-workaround"), wait_until="networkidle")
            wait_rows(p)
            reqs = data_reqs(s, i0)
            s.check("infinite(workaround): data requests return rows", len(reqs) >= 1 and len(rows(p, "name")) > 0, {"reqs": reqs[:1], "rows": len(rows(p, "name"))})
            sort_by(p, "age")
            ages = [int(v) for v in cell_values(p, "age") if v.isdigit()]
            dbmin = db("select min(age) from friend")[0][0]
            s.check("infinite: sort asc by age matches db", bool(ages) and ages[0] == dbmin and ages == sorted(ages), {"first": ages[:8], "db_min": dbmin})
            sort_by(p, "age")
            sort_by(p, "age")
            some_name = db("select name from friend order by id desc limit 1")[0][0]
            sub = some_name.split()[-1][:4]
            text_filter(p, "name", sub)
            names = cell_values(p, "name")
            exp = db("select count(*) from friend where lower(name) like ?", f"%{sub.lower()}%")[0][0]
            s.check("infinite: text filter matches db", bool(names) and all(sub.lower() in n.lower() for n in names) and len(names) == min(exp, 50), {"sub": sub, "shown": len(names), "blank_rows": sum(1 for n in names if not n), "db": exp})
            s.shot(p, "infinite-filtered")
            text_filter(p, "name", "")
            wait_rows(p)
            first = rows(p, "id")[0]["val"]
            edit_cell(p, first, "age", 77)
            got = db("select age from friend where id=?", int(first))[0][0]
            s.check("infinite: numeric cell edit updates sqlite", got == 77, {"id": first, "db_age": got})
            # add via dialog
            before = count()
            p.click("button:has(svg.lucide-plus)")
            p.wait_for_selector("[role=dialog]", timeout=5000)
            dlg = p.locator("[role=dialog]")
            dlg.locator("input[name=name]").fill("QA Added Friend")
            dlg.locator("input[name=age]").fill("33")
            dlg.locator("input[name=years_known]").fill("3")
            met = os.environ.get("QA_ADD_MET", "2020-01-02T03:04:05")
            if met and dlg.locator("input[name=met]").count():
                dlg.locator("input[name=met]").fill(met)
            s.note(f"add dialog: met field value submitted = {met!r}")
            s.shot(p, "add-dialog")
            dlg.locator("button:has-text('Add')").click()
            p.wait_for_timeout(3000)
            after = count()
            added = db("select id, name, age, years_known, met, owes_me from friend where name='QA Added Friend'")
            s.check("infinite: add dialog inserts row", after == before + 1 and bool(added), {"before": before, "after": after, "row": added[-1:] if added else None})
            s.check("infinite: add dialog closes after submit", p.locator("[role=dialog]").count() == 0, p.locator("[role=dialog]").count())
            if p.locator("[role=dialog]").count():
                p.keyboard.press("Escape")
            # select two rows and delete
            wait_rows(p)
            ids = [r["val"] for r in rows(p, "id")[:2]]
            boxes = p.locator(".ag-row .ag-selection-checkbox input")
            boxes.nth(0).click()
            boxes.nth(1).click()
            p.wait_for_timeout(1200)
            before = count()
            p.click("button:has(svg.lucide-trash-2)")
            p.wait_for_timeout(3000)
            after = count()
            gone = [i for i in ids if not db("select 1 from friend where id=?", int(i))]
            s.check("infinite: delete_selected removes the 2 selected rows from sqlite", after == before - 2 and len(gone) == 2, {"before": before, "after": after, "ids": ids, "gone": gone})
            s.shot(p, "after-delete")

        run_step(s, "infinite workaround flow", workaround)

    for key, route in (("simple", "/model"), ("auth", "/model-auth")):
        if key not in pages:
            continue
        ctx = s.new_context(key)
        p = ctx.new_page()

        def broken(route=route, key=key):
            i0 = len(s.requests)
            n_http = len(s.http_errors)
            p.goto(base + route, wait_until="networkidle")
            if key == "auth":
                p.click("button:has-text('Login')")
            p.wait_for_timeout(4000)
            errs = [e for e in s.http_errors[n_http:] if "/abstract-wrapper-data" in e["url"]]
            n = len([r for r in rows(p, "name") if r["val"]])
            s.check(f"{route}: data endpoint has no HTTP errors", not errs, errs[:2])
            s.check(f"{route}: grid shows db rows (db has {count()})", n > 0, n)
            s.shot(p, key)

        run_step(s, f"{route} flow", broken)
    s.note(f"db rows at end: {count()}")
