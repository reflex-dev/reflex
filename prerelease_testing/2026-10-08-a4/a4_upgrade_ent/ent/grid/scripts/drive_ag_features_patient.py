"""(a3_ent_grid patient copy: goto() also waits for every grid header) Drive the advanced AG Grid demo pages (master-detail, tree, pivot, cell selection,
fill handle, clipboard, aligned grids, editable, state grid, selected items) and the
QA extension pages (row_id_key, pinned rows + aliases, overlays, renderer/editor,
memo grid, ComponentState grids).

Usage: drive_ag_features.py <base_url> <out_dir> <expected_venv> [scenario,...]
"""

import re
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session, assert_driver_and_server  # noqa: E402

base, out, venv = sys.argv[1:4]
only = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else None
info = assert_driver_and_server(venv)


def G(gid):
    return f'[grid-id="{gid}"]'


def body_rows(page, gid, col):
    return page.evaluate(
        """([gid, col]) => [...document.querySelectorAll(`[grid-id="${gid}"] .ag-grid-scrolling-container .ag-row`)]
          .map(r => ({idx: +r.getAttribute('row-index'), id: r.getAttribute('row-id'), sel: r.getAttribute('aria-selected'),
                      val: ((r.querySelector(`.ag-cell[col-id="${col}"]`) || {}).innerText || '').trim()}))
          .filter(r => !Number.isNaN(r.idx)).sort((a, b) => a.idx - b.idx)""",
        [gid, col],
    )


def cell(page, gid, row_index, col):
    return page.locator(f'{G(gid)} .ag-grid-scrolling-container .ag-row[row-index="{row_index}"] .ag-cell[col-id="{col}"]').first


def headers(page, gid):
    return page.locator(f"{G(gid)} .ag-header-cell-text").all_inner_texts()


def toasts(page):
    return page.locator("[data-sonner-toast]").all_inner_texts()


def goto(page, route):
    page.goto(base + route, wait_until="networkidle")
    page.wait_for_timeout(2000)
    # a3_ent_grid "patient" variant (for a heavily loaded machine, dev mode): additionally wait up to 30 s until every
    # AG Grid on the page has rendered header cells, then let it settle.
    try:
        page.wait_for_function(
            "() => { const g = [...document.querySelectorAll('.ag-root-wrapper')]; return g.length && g.every(w => w.querySelector('.ag-header-cell')); }",
            timeout=30000,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[NOTE] patient wait timed out on {route}: {e!r}"[:200], flush=True)
    page.wait_for_timeout(1500)


SCENARIOS = {}


def scenario(fn):
    SCENARIOS[fn.__name__] = fn
    return fn


@scenario
def master_detail(s, p):
    goto(p, "/master-detail")
    for gid in ("state-vars-grid", "static-objects-grid"):
        p.locator(f"{G(gid)} .ag-row[row-index='0'] .ag-group-contracted").first.click()
        p.wait_for_timeout(1500)
        detail = p.locator(f"{G(gid)} .ag-details-row").first
        txt = detail.inner_text() if detail.count() else ""
        s.check(f"master-detail[{gid}]: expanding row 0 shows detail grid", "Stock Level" in txt and "10" in txt, txt[:200])
    s.shot(p, "master-detail")


@scenario
def tree(s, p):
    goto(p, "/tree")
    gid = "ag_grid_tree_1"
    top = p.locator(f"{G(gid)} .ag-row-level-0 .ag-group-value").all_inner_texts()
    s.check("tree: top-level groups are folders (combine hosts on)", {"Desktop", "Documents"} <= set(top), top)
    p.locator(f"{G(gid)} .ag-row-level-0").filter(has_text="Documents").locator(".ag-group-contracted").first.click()
    p.wait_for_timeout(800)
    lvl1 = p.locator(f"{G(gid)} .ag-row-level-1 .ag-group-value").all_inner_texts()
    s.check("tree: expanding Documents shows Work/Personal", {"Work", "Personal"} <= set(lvl1), lvl1)
    agg = p.locator(f"{G(gid)} .ag-row-level-0").filter(has_text="Documents").locator('.ag-cell[col-id="size"]').first.inner_text()
    s.check("tree: aggregated size uses JS value_formatter (MB/KB)", agg.endswith(("MB", "KB")), agg)
    p.click(".rt-SwitchRoot")
    p.wait_for_timeout(2500)
    top2 = p.locator(f"{G(gid)} .ag-row-level-0 .ag-group-value").all_inner_texts()
    s.check("tree: toggling Combine Hosts re-keys grid with hosts at top level", {"vali", "vidar"} <= set(top2), top2)
    p.click("button:has-text('Save column state')")
    p.wait_for_timeout(1500)
    ls = p.evaluate("() => Object.fromEntries(Object.entries(localStorage).filter(([k]) => k.includes('column_state')).map(([k, v]) => [k, v.slice(0, 120)]))")
    s.check("tree: Save column state writes LocalStorage var", bool(ls) and any("colId" in v for v in ls.values()), ls)
    enabled = p.locator("button:has-text('Load column state')").is_enabled()
    s.check("tree: Load column state button enabled after save (computed var from LocalStorage)", enabled, enabled)
    p.reload(wait_until="networkidle")
    p.wait_for_timeout(2000)
    s.check("tree: Load column state still enabled after reload", p.locator("button:has-text('Load column state')").is_enabled(), "")
    p.click("button:has-text('Load column state')")
    p.wait_for_timeout(1000)
    s.shot(p, "tree")


@scenario
def pivot(s, p):
    goto(p, "/pivot")
    gid = "sandbox_grid"
    hdr = p.locator(f"{G(gid)} .ag-header-group-cell, {G(gid)} .ag-header-cell").all_inner_texts()
    joined = " | ".join(h.strip() for h in hdr if h.strip())
    s.check("pivot: pivot headers by sport (virtualised) with sum(Gold) value columns", "Biathlon" in joined and "sum(Gold)" in joined, joined[:300])
    groups = p.locator(f"{G(gid)} .ag-row-level-0 .ag-group-value").all_inner_texts()
    s.check("pivot: rows grouped by country", "United States" in groups, groups[:6])
    s.check("pivot: pivot panel + columns side bar visible", p.locator(f"{G(gid)} .ag-pivot-mode-panel, {G(gid)} .ag-column-drop").count() > 0 and p.locator(f"{G(gid)} .ag-side-bar").count() > 0, "")
    s.shot(p, "pivot")


@scenario
def cell_selection(s, p):
    goto(p, "/cell-selection")
    gid = "cell_selection_grid"
    a = cell(p, gid, 0, "athlete").bounding_box()
    b = cell(p, gid, 2, "country").bounding_box()
    p.mouse.move(a["x"] + 10, a["y"] + 10)
    p.mouse.down()
    p.mouse.move(b["x"] + 20, b["y"] + 10, steps=12)
    p.mouse.up()
    p.wait_for_timeout(1500)
    t = toasts(p)
    s.check("cell-selection: range drag fires on_cell_selection_changed(finished) -> toast", any("Selected cells" in x and "startRow" in x for x in t), [x[:200] for x in t])
    s.check("cell-selection: highlighted cells match reported range (3 rows x 2 cols)", p.locator(f"{G(gid)} .ag-cell-range-selected").count() == 6, p.locator(f"{G(gid)} .ag-cell-range-selected").count())
    s.shot(p, "cell-selection")


@scenario
def fill_handle(s, p):
    goto(p, "/fill-handle")
    gid = "fill-handle-grid"
    cell(p, gid, 0, "age").click()
    p.wait_for_timeout(500)
    fh = p.locator(f"{G(gid)} .ag-fill-handle").first
    box = fh.bounding_box()
    tgt = cell(p, gid, 2, "age").bounding_box()
    s.check("fill-handle: handle visible on selected cell", box is not None, box)
    p.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    p.mouse.down()
    p.mouse.move(tgt["x"] + tgt["width"] / 2, tgt["y"] + tgt["height"] / 2, steps=15)
    p.mouse.up()
    p.wait_for_timeout(2000)
    ages = [r["val"] for r in body_rows(p, gid, "age")[:4]]
    t = toasts(p)
    s.check("fill-handle: dragging fills rows 1-2 and fires on_cell_value_changed toasts", ages[1:3] != ["19", "27"] and any("Updated age" in x for x in t), {"ages": ages, "toasts": t[:4]})
    p.reload(wait_until="networkidle")
    p.wait_for_timeout(2000)
    ages2 = [r["val"] for r in body_rows(p, gid, "age")[:4]]
    s.check("fill-handle: filled values persisted in State across reload", ages2 == ages, {"before_reload": ages, "after_reload": ages2})
    s.shot(p, "fill-handle")
    # clipboard: copy gold of row 0 (8) to row 4 (2)
    p.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=base)
    cell(p, gid, 0, "gold").click()
    p.keyboard.press("Control+c")
    p.wait_for_timeout(500)
    cell(p, gid, 4, "gold").click()
    p.keyboard.press("Control+v")
    p.wait_for_timeout(2000)
    golds = [r["val"] for r in body_rows(p, gid, "gold")[:5]]
    t = toasts(p)
    s.check("clipboard: Ctrl+C/Ctrl+V copies gold row0 -> row4 and fires change event", golds[4] == golds[0] and any("Updated gold" in x for x in t), {"golds": golds, "toasts": t[:4]})


@scenario
def aligned(s, p):
    goto(p, "/aligned-grids")
    s.check("aligned: both grids show data", len(body_rows(p, "grid1", "athlete")) > 0 and len(body_rows(p, "grid2", "athlete")) > 0, "")
    before = (p.locator(f"{G('grid1')} .ag-header-cell[col-id='gold']").count(), p.locator(f"{G('grid2')} .ag-header-cell[col-id='gold']").count())
    p.locator(f"{G('grid1')} .ag-header-group-cell").filter(has_text="Medals").locator(".ag-header-expand-icon:visible, .ag-header-icon:visible").first.click()
    p.wait_for_timeout(1200)
    after = (p.locator(f"{G('grid1')} .ag-header-cell[col-id='gold']").count(), p.locator(f"{G('grid2')} .ag-header-cell[col-id='gold']").count())
    s.check("aligned: expanding Medals group in grid1 also expands grid2", before == (0, 0) and after == (1, 1), {"before": before, "after": after})
    w1 = p.locator(f"{G('grid1')} .ag-header-cell[col-id='athlete']").bounding_box()["width"]
    handle = p.locator(f"{G('grid1')} .ag-header-cell[col-id='athlete'] .ag-header-cell-resize").first.bounding_box()
    p.mouse.move(handle["x"] + 2, handle["y"] + handle["height"] / 2)
    p.mouse.down()
    p.mouse.move(handle["x"] + 120, handle["y"] + handle["height"] / 2, steps=10)
    p.mouse.up()
    p.wait_for_timeout(800)
    w1b = p.locator(f"{G('grid1')} .ag-header-cell[col-id='athlete']").bounding_box()["width"]
    w2b = p.locator(f"{G('grid2')} .ag-header-cell[col-id='athlete']").bounding_box()["width"]
    s.check("aligned: resizing athlete column in grid1 resizes grid2", w1b > w1 + 50 and abs(w1b - w2b) < 2, {"w1_before": w1, "w1_after": w1b, "w2_after": w2b})
    s.shot(p, "aligned")


@scenario
def editable(s, p):
    goto(p, "/editable")
    gid = "editable-grid"
    cell(p, gid, 0, "name").dblclick()
    p.wait_for_timeout(400)
    ed = p.locator(f"{G(gid)} .ag-cell-inline-editing input").first
    ed.fill("Johnny")
    ed.press("Enter")
    p.wait_for_timeout(1500)
    t = toasts(p)
    s.check("editable: edit fires on_cell_value_changed toast", any("Cell value changed: name = Johnny" in x for x in t), t[:3])
    p.reload(wait_until="networkidle")
    p.wait_for_timeout(1500)
    names = [r["val"] for r in body_rows(p, gid, "name")]
    s.check("editable: edited value persisted in State across reload", names[:1] == ["Johnny"], names)


@scenario
def state_grid(s, p):
    goto(p, "/state-grid")
    gid = "ag_grid_state"
    p.click("button:has-text('Load Columns')")
    p.wait_for_timeout(1000)
    h = headers(p, gid)
    s.check("state-grid: Load Columns sets header_name/headerName from State", [x for x in h if x.strip()][-3:] == ["DIR", "STR", "HZ"], h)
    p.click(".rt-SwitchRoot")
    p.click("button:has-text('Load Data')")
    p.wait_for_timeout(2000)
    r = body_rows(p, gid, "frequency")
    s.check("state-grid: data loaded with JS value_formatter suffix", bool(r) and r[0]["val"].endswith("Hz"), r[:2])
    sel = [x["sel"] for x in r]
    s.check("state-grid: on_row_data_updated event chain selected all rows (select_all_on_load)", bool(sel) and all(x == "true" for x in sel), sel[:5])
    sw = p.locator(".rt-SwitchRoot").get_attribute("data-state")
    s.check("state-grid: chained set_select_all_on_load(False) reset the switch", sw == "unchecked", sw)
    p.click("button:has-text('Clear Data')")
    p.wait_for_timeout(1000)
    s.check("state-grid: Clear Data empties grid", len(body_rows(p, gid, "frequency")) == 0, "")
    p.click("button:has-text('Clear Columns')")
    p.wait_for_timeout(1000)
    s.check("state-grid: Clear Columns removes headers", not [x for x in headers(p, gid) if x.strip()], headers(p, gid))


@scenario
def selected_items(s, p):
    goto(p, "/selected-items")
    p.click("button:has-text('Select All')")
    p.wait_for_timeout(2000)
    hd = p.get_by_text(re.compile(r"Selected Items \(\d+\)")).first.inner_text()
    s.check("selected-items: Select All -> on_selection_changed -> State count", hd != "Selected Items (0)", hd)
    p.click("button:has-text('Deselect All')")
    p.wait_for_timeout(1500)
    inp = p.locator("input[class*=TagsInput], .mantine-TagsInput-inputField, input[placeholder]").first
    inp.click()
    inp.type("n")
    inp.press("Enter")
    p.wait_for_timeout(2000)
    hd2 = p.get_by_text(re.compile(r"Selected Items \(\d+\)")).first.inner_text()
    n_dir_n = sum(1 for r in body_rows(p, "ag_grid_basic_1", "direction") if r["val"] == "N" and r["sel"] == "true")
    s.check("selected-items: tags input 'n' -> upper-cased key -> select_rows_by_key(direction=N)", hd2 != "Selected Items (0)" and n_dir_n > 0, {"heading": hd2, "visible_selected_N_rows": n_dir_n})
    s.shot(p, "selected-items")


@scenario
def integrated_charts(s, p):
    goto(p, "/integrated-charts")
    gid = "ag_grid_integrated_charts"
    a = cell(p, gid, 0, "direction").bounding_box()
    b = cell(p, gid, 5, "frequency").bounding_box()
    p.mouse.move(a["x"] + 5, a["y"] + 5)
    p.mouse.down()
    p.mouse.move(b["x"] + 20, b["y"] + 10, steps=10)
    p.mouse.up()
    cell(p, gid, 3, "strength").click(button="right")
    p.wait_for_timeout(800)
    p.locator(".ag-menu-option").filter(has_text="Chart Range").first.hover()
    p.wait_for_timeout(600)
    p.locator(".ag-menu-option").filter(has_text="Column").first.hover()
    p.wait_for_timeout(600)
    p.locator(".ag-menu-option").filter(has_text="Grouped").first.click()
    p.wait_for_timeout(3000)
    s.check("integrated-charts: chart range -> chart dialog with canvas", p.locator(".ag-chart canvas, .ag-chart-wrapper canvas, .ag-chart-components-wrapper canvas").count() > 0, p.locator("canvas").count())
    s.shot(p, "integrated-chart")


@scenario
def qa_props(s, p):
    goto(p, "/qa-grid-props")
    gid = "qa_rowid_grid"
    ids = [r["id"] for r in body_rows(p, gid, "uid")]
    s.check("row_id_key: getRowId uses data.uid", ids == ["u-1", "u-2", "u-3"], ids)
    top = p.locator(f"{G(gid)} .ag-grid-pinned-top-rows-container .ag-row").all_inner_texts()
    bot = p.locator(f"{G(gid)} .ag-grid-pinned-bottom-rows-container .ag-row").all_inner_texts()
    s.check("pinned rows (new names pinned_top_row_data/pinned_bottom_row_data)", any("TOP-NEW" in x for x in top) and any("BOT-NEW" in x for x in bot), {"top": top, "bottom": bot})
    top = p.locator(f"{G('qa_alias_grid')} .ag-grid-pinned-top-rows-container .ag-row").all_inner_texts()
    bot = p.locator(f"{G('qa_alias_grid')} .ag-grid-pinned-bottom-rows-container .ag-row").all_inner_texts()
    s.check("pinned rows (legacy aliases pinned_row_top_data/pinned_row_bottom_data)", any("TOP-OLD" in x for x in top) and any("BOT-OLD" in x for x in bot), {"top": top, "bottom": bot})
    d = p.locator(f"{G('qa_empty_default')} .ag-overlay:not(.ag-hidden)").all_inner_texts()
    sp = p.locator(f"{G('qa_empty_suppressed')} .ag-overlay:not(.ag-hidden)").all_inner_texts()
    s.check("suppress_overlays=['noRows'] hides the no-rows overlay (default grid shows it)", any("No Rows" in x for x in d) and not any("No Rows" in x for x in sp), {"default": d, "suppressed": sp})
    q = [r["val"] for r in body_rows(p, gid, "qty")]
    s.check("value_formatter string renders 'N units'", q[:1] == ["1 units"], q)
    badges = p.locator(f"{G(gid)} .qa-status-badge").all_inner_texts()
    s.check("custom JS cell renderer (rx.badge via ArgsFunctionOperation) renders", "S:new" in [b.replace(" ", "") for b in badges], badges)
    p.click("#qa-prepend")
    p.wait_for_timeout(1200)
    ids2 = [r["id"] for r in body_rows(p, gid, "uid")]
    s.check("row_id_key: prepending a row keeps stable ids", ids2 == ["u-4", "u-1", "u-2", "u-3"], ids2)
    p.click("#qa-bump")
    p.wait_for_timeout(1200)
    q2 = {r["id"]: r["val"] for r in body_rows(p, gid, "qty")}
    s.check("row_id_key: immutable State update bumps u-2 in place", q2.get("u-2") == "12 units", q2)
    st = p.locator(f'{G(gid)} .ag-row[row-id="u-1"] .ag-cell[col-id="status"]').first
    st.dblclick()
    p.wait_for_timeout(800)
    opt = p.locator(".ag-select-list .ag-list-item, .ag-list-item, [role=option]").filter(has_text="done").first
    if opt.count():
        opt.click()
    else:
        p.keyboard.press("ArrowDown")
        p.keyboard.press("ArrowDown")
    p.keyboard.press("Enter")
    p.wait_for_timeout(1500)
    edits = p.locator("#qa-edits").inner_text()
    shown = p.locator(f'{G(gid)} .ag-row[row-id="u-1"] .qa-status-badge').inner_text().replace(" ", "")
    s.check("select cell editor edit -> on_cell_value_changed node_id == row_id_key uid -> State", "u-1:status->" in edits and shown.startswith("S:") and shown != "S:new", {"edits": edits, "badge": shown})
    # clipboard on a grid that registers ClipboardModule
    p.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=base)
    cg = "qa_clip_grid"
    cell(p, cg, 0, "b").click()
    p.keyboard.press("ControlOrMeta+c")
    p.wait_for_timeout(600)
    clip = p.evaluate("() => navigator.clipboard.readText()")
    cell(p, cg, 2, "b").click()
    p.keyboard.press("ControlOrMeta+v")
    p.wait_for_timeout(1500)
    vals = [r["val"] for r in body_rows(p, cg, "b")]
    log = p.locator("#qa-clip-log").inner_text()
    s.check("clipboard (ClipboardModule): Ctrl+C copies cell, Ctrl+V pastes + fires on_cell_value_changed", clip.strip() == "10" and vals[2] == "10" and "2:b=10" in log, {"clipboard": clip, "b": vals, "log": log})
    s.shot(p, "qa-props")


@scenario
def qa_memo(s, p):
    goto(p, "/qa-grid-memo")
    gid = "qa_memo_grid"
    s.check("memo grid: column defs from State.fields.foreach", [x for x in headers(p, gid) if x.strip()] == ["Name", "Qty"], headers(p, gid))
    cell(p, gid, 1, "name").click()
    p.wait_for_timeout(1200)
    s.check("memo grid: on_cell_clicked inside @rx.memo reaches State", "name=beta" in p.locator("#qa-clicked").inner_text(), p.locator("#qa-clicked").inner_text())
    p.click("#qa-toggle-col")
    p.wait_for_timeout(1200)
    s.check("memo grid: toggling State field list adds Status column", "Status" in headers(p, gid), headers(p, gid))
    p.click("#qa_cs_a-add")
    p.click("#qa_cs_a-add")
    p.wait_for_timeout(1500)
    ca, cb = p.locator("#qa_cs_a-count").inner_text(), p.locator("#qa_cs_b-count").inner_text()
    ra, rb = len(body_rows(p, "qa_cs_a", "k")), len(body_rows(p, "qa_cs_b", "k"))
    s.check("ComponentState grids: instance A grows independently of B", (ca, cb, ra, rb) == ("rows: 3", "rows: 1", 3, 1), {"a": ca, "b": cb, "rows_a": ra, "rows_b": rb})
    p.reload(wait_until="networkidle")
    p.wait_for_timeout(2000)
    s.check("ComponentState grids: state survives reload", len(body_rows(p, "qa_cs_a", "k")) == 3, len(body_rows(p, "qa_cs_a", "k")))
    s.shot(p, "qa-memo")


with Session(f"ag_features-{venv}", Path(out)) as s:
    s.note(f"guard: {info['versions']}")
    for name, fn in SCENARIOS.items():
        if only and name not in only:
            continue
        ctx = s.new_context(name)
        page = ctx.new_page()
        try:
            fn(s, page)
        except Exception as e:  # noqa: BLE001
            s.check(f"{name}: scenario completed", False, f"exception: {e!r}"[:500])
            traceback.print_exc(limit=2)
            s.shot(page, f"{name}-exception")
