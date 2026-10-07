"""Playwright driver for the dataeditor_components cluster app.

Usage (driver venv):
  NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
    $SB/envs/driver/bin/python driver.py <base_url> <outdir> [--groups g1,g2] [--label alpha-dev]

Writes <outdir>/results.json (per-check pass/fail + captured console/page errors/failed
requests per group) and screenshots under <outdir>/shots/.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path

import playwright

assert "/envs/driver/" in playwright.__file__, playwright.__file__

from playwright.sync_api import Page, sync_playwright  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
import pngutil  # noqa: E402

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = [
    re.compile(r"Hey developer.*HydrateFallback|reactrouter\.com/start/framework/route-module"),
    re.compile(r"\[vite\] (connecting|connected)"),
    re.compile(r"Download the React DevTools"),
]


def benign(t: str) -> bool:
    return any(p.search(t) for p in BENIGN)


class Run:
    def __init__(self, base: str, out: Path, label: str):
        self.base = base.rstrip("/")
        self.out = out
        self.label = label
        (out / "shots").mkdir(parents=True, exist_ok=True)
        self.results: dict = {"base": base, "label": label, "groups": {}}
        self.group = None

    def start_group(self, name: str):
        self.group = {"checks": [], "console": [], "pageerrors": [], "failed_requests": [], "http_errors": [], "notes": [], "ws": {"sent": 0, "recv": 0}}
        self.results["groups"][name] = self.group
        self.gname = name

    def check(self, name: str, ok: bool, detail=None):
        self.group["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
        print(f"  [{'PASS' if ok else 'FAIL'}] {self.gname}/{name}: {str(detail)[:300] if detail is not None else ''}", flush=True)

    def note(self, msg):
        self.group["notes"].append(msg)
        print(f"  [note] {self.gname}: {str(msg)[:300]}", flush=True)

    def shot(self, page: Page, name: str, full=False, clip=None):
        p = self.out / "shots" / f"{self.label}-{name}.png"
        if clip:
            page.screenshot(path=str(p), clip=clip)
        else:
            page.screenshot(path=str(p), full_page=full)
        return str(p)

    def attach(self, page: Page):
        g = lambda: self.group  # noqa: E731
        page.on("console", lambda m: g()["console"].append({"type": m.type, "text": m.text[:1500], "loc": (m.location or {}).get("url", "")[-120:]}) if not benign(m.text) else None)
        page.on("pageerror", lambda e: g()["pageerrors"].append(e.stack))
        page.on("requestfailed", lambda r: g()["failed_requests"].append({"url": r.url[:300], "failure": r.failure}) if not r.url.startswith("data:") else None)
        page.on("response", lambda r: g()["http_errors"].append({"url": r.url[:300], "status": r.status}) if r.status >= 400 else None)

        def on_ws(ws):
            ws.on("framesent", lambda f: g()["ws"].__setitem__("sent", g()["ws"]["sent"] + 1))
            ws.on("framereceived", lambda f: g()["ws"].__setitem__("recv", g()["ws"]["recv"] + 1))
        page.on("websocket", on_ws)

    def goto(self, page: Page, path: str, wait_sel: str | None = None, timeout=90000):
        page.goto(self.base + path, wait_until="domcontentloaded", timeout=timeout)
        if wait_sel:
            page.wait_for_selector(wait_sel, timeout=timeout)
        # wait for websocket hydration: the version banner is static, so wait for a state-driven node
        page.wait_for_timeout(1500)


def text(page: Page, sel: str) -> str:
    return page.locator(sel).first.inner_text(timeout=15000)


def wait_text(page: Page, sel: str, pred, timeout=20000) -> str:
    end = time.time() + timeout / 1000
    last = None
    while time.time() < end:
        try:
            last = page.locator(sel).first.inner_text(timeout=2000)
            if pred(last):
                return last
        except Exception as e:  # noqa: BLE001
            last = f"<{type(e).__name__}>"
        page.wait_for_timeout(200)
    return last


def grid_canvas_box(page: Page, box_sel: str):
    c = page.locator(f"{box_sel} canvas").first
    c.wait_for(state="visible", timeout=60000)
    return c.bounding_box()


def cell_xy(box, col_widths, col, row, row_h, header_h=36, marker=0):
    x = box["x"] + marker + sum(col_widths[:col]) + col_widths[col] / 2
    y = box["y"] + header_h + row * row_h + row_h / 2
    return x, y


GRID_JS = """
(sel) => {
  const box = typeof sel === 'string' ? document.querySelector(sel) : sel;
  const canvas = box && box.querySelector('canvas[data-testid=data-grid-canvas]');
  if (!canvas) return {err: 'no canvas'};
  const fk = Object.keys(canvas).find(k => k.startsWith('__reactFiber$'));
  let f = canvas[fk], best = null;
  while (f) {
    const p = f.memoizedProps;
    if (p && typeof p.getCellContent === 'function' && Array.isArray(p.columns) && typeof p.rows === 'number') best = f;
    f = f.return;
  }
  if (!best) return {err: 'no getCellContent fiber'};
  const p = best.memoizedProps;
  const out = {};
  for (let r = 0; r < Math.min(p.rows, 40); r++) {
    for (let c = 0; c < p.columns.length; c++) {
      let cell;
      try { cell = p.getCellContent([c, r]); } catch (e) { out[c + '-' + r] = {err: String(e)}; continue; }
      out[c + '-' + r] = {kind: cell.kind, data: cell.data, display: cell.displayData, ro: cell.readonly, ov: cell.allowOverlay};
    }
  }
  return {rows: p.rows, titles: p.columns.map(c => c.title), types: p.columns.map(c => c.type), cells: out};
}
"""


def grid_cells(page: Page, box_sel: str):
    """Read cells via the DataEditor fiber's getCellContent prop (what Reflex's formatDataEditorCells returns)."""
    try:
        return page.evaluate(GRID_JS, box_sel)
    except Exception as e:  # noqa: BLE001
        return {"err": f"{type(e).__name__}: {e}"}


def cell_values(g, col=None):
    if not g or "cells" not in g:
        return []
    return [v.get("display") if v.get("display") is not None else v.get("data") for k, v in sorted(g["cells"].items(), key=lambda kv: (int(kv[0].split("-")[1]), int(kv[0].split("-")[0]))) if col is None or int(k.split("-")[0]) == col]


MAIN_W = [90, 60, 70, 60, 130, 80, 80, 80, 80, 70, 90, 60]


def g_de_main(run: Run, page: Page):
    run.goto(page, "/de", "#de-main-box canvas")
    page.wait_for_timeout(3000)
    run.shot(page, "de-initial", full=True)
    # carousel CSS presence before opening overlay
    css = page.evaluate(
        """() => {
          const hits = [];
          for (const s of document.styleSheets) {
            let rules; try { rules = s.cssRules; } catch (e) { hits.push({href: s.href, err: String(e)}); continue; }
            const txt = Array.from(rules).map(r => r.cssText).join('\\n');
            if (txt.includes('.carousel')) hits.push({href: s.href, owner: s.ownerNode && (s.ownerNode.getAttribute('data-vite-dev-id') || s.ownerNode.tagName), carousel: true, n: rules.length});
            else if (txt.includes('gdg-')) hits.push({href: s.href, owner: s.ownerNode && (s.ownerNode.getAttribute('data-vite-dev-id') || s.ownerNode.tagName), glide: true, n: rules.length});
          }
          return hits;
        }"""
    )
    run.check("carousel_css_loaded_on_page", any(h.get("carousel") for h in css), css)
    run.check("glide_css_loaded_on_page", any(h.get("glide") for h in css), css)
    cells = grid_cells(page, "#de-main-box")
    run.group["grid_cells"] = cells
    if cells and "cells" in cells:
        kinds = {cells["titles"][c]: (cells["cells"].get(f"{c}-0") or {}).get("kind") for c in range(len(cells["titles"]))}
        disp = {cells["titles"][c]: (cells["cells"].get(f"{c}-0") or {}).get("display") for c in range(len(cells["titles"]))}
        run.note({"row0_kinds": kinds, "row0_display": disp})
        img = [(cells["cells"].get(f"4-{r}") or {}) for r in range(8)]
        run.check("image_cells_kind_image_with_url_arrays", all(i.get("kind") == "image" and isinstance(i.get("data"), list) for i in img), [(i.get("kind"), i.get("data")) for i in img])
        unsupported = {t: disp.get(t) for t in ("Link", "Notes", "Tags", "Drill", "RowID")}
        run.check("unsupported_types_render_type_name_instead_of_data(pre-existing)", all(unsupported[t] == ty for t, ty in zip(("Link", "Notes", "Tags", "Drill", "RowID"), ("uri", "markdown", "bubble", "drilldown", "row-id"))), unsupported)
    else:
        run.check("grid_cells_readable", False, cells)
    box = grid_canvas_box(page, "#de-main-box")
    run.note({"canvas_box": box})
    # click a text cell (col 0,row 0) -> on_cell_clicked
    x, y = cell_xy(box, MAIN_W, 0, 0, 60, marker=32)
    page.mouse.click(x, y)
    t = wait_text(page, "#last-click", lambda s: "0,0" in s)
    run.check("on_cell_clicked_text_cell", "0,0" in (t or ""), t)
    # click image cell row 1 (multi local) -> on_cell_clicked
    x, y = cell_xy(box, MAIN_W, 4, 1, 60, marker=32)
    page.mouse.click(x, y)
    t = wait_text(page, "#last-click", lambda s: "4,1" in s)
    run.check("on_cell_clicked_image_cell", "4,1" in (t or ""), t)
    run.shot(page, "de-image-selected", clip={"x": box["x"], "y": box["y"], "width": box["width"], "height": box["height"]})


def overlay_state(page: Page):
    return page.evaluate(
        """() => {
          const portal = document.getElementById('portal');
          const car = document.querySelector('.carousel.carousel-slider') || document.querySelector('.carousel');
          const res = {portal_html_len: portal ? portal.innerHTML.length : null, has_carousel: !!car};
          if (!car) { res.portal_html = portal ? portal.innerHTML.slice(0, 600) : null; return res; }
          const wrap = car.querySelector('.slider-wrapper') || car;
          const wr = wrap.getBoundingClientRect();
          const imgs = Array.from(car.querySelectorAll('img'));
          const vis = imgs.filter(im => { const r = im.getBoundingClientRect(); const cx = Math.max(0, Math.min(r.right, wr.right) - Math.max(r.left, wr.left)); const cy = Math.max(0, Math.min(r.bottom, wr.bottom) - Math.max(r.top, wr.top)); return cx * cy > 4 && r.width > 0; });
          const cs = getComputedStyle(car), ws = getComputedStyle(wrap);
          const slider = car.querySelector('.slider');
          return Object.assign(res, {
            wrapper_rect: [wr.x, wr.y, wr.width, wr.height],
            carousel_overflow: cs.overflow, carousel_position: cs.position,
            wrapper_overflow: ws.overflow,
            slider_display: slider ? getComputedStyle(slider).display : null,
            n_imgs: imgs.length, n_visible_imgs: vis.length,
            visible_srcs: vis.map(i => i.getAttribute('src')),
            img_complete: imgs.map(i => [i.getAttribute('src'), i.complete, i.naturalWidth]),
            has_arrows: !!car.querySelector('.control-arrow'),
            has_dots: !!car.querySelector('.control-dots'),
          });
        }"""
    )


def open_image_overlay(run: Run, page: Page, box, row: int, name: str):
    x, y = cell_xy(box, MAIN_W, 4, row, 60, marker=32)
    page.mouse.click(x, y)
    page.wait_for_timeout(300)
    page.mouse.dblclick(x, y)
    page.wait_for_timeout(1500)
    st = overlay_state(page)
    if not st.get("has_carousel"):
        page.keyboard.press("Enter")
        page.wait_for_timeout(1500)
        st = overlay_state(page)
        st["opened_via"] = "Enter"
    run.shot(page, f"overlay-{name}", full=False)
    return st


def g_de_overlay(run: Run, page: Page):
    run.goto(page, "/de", "#de-main-box canvas")
    page.wait_for_timeout(3000)
    box = grid_canvas_box(page, "#de-main-box")
    for row, name, expect_multi in ((1, "multi-local", True), (0, "single-local", False), (3, "multi-remote", True), (4, "xorigin-nocors", False), (7, "mixed", True)):
        st = open_image_overlay(run, page, box, row, name)
        styled = st.get("has_carousel") and st.get("n_visible_imgs") == 1 and st.get("slider_display") == "flex"
        run.check(f"overlay_{name}_styled_single_visible", bool(styled), st)
        if expect_multi:
            run.check(f"overlay_{name}_has_arrows", bool(st.get("has_arrows")), {k: st.get(k) for k in ("has_arrows", "has_dots", "n_imgs")})
            if st.get("has_arrows"):
                before = st.get("visible_srcs")
                nxt = page.locator(".carousel .control-next").first
                try:
                    nxt.click(timeout=3000)
                    page.wait_for_timeout(800)
                    st2 = overlay_state(page)
                    run.check(f"overlay_{name}_next_arrow_changes_slide", st2.get("visible_srcs") != before and st2.get("n_visible_imgs") == 1, {"before": before, "after": st2.get("visible_srcs"), "n_visible": st2.get("n_visible_imgs")})
                    run.shot(page, f"overlay-{name}-next")
                except Exception as e:  # noqa: BLE001
                    run.check(f"overlay_{name}_next_arrow_changes_slide", False, repr(e)[:300])
        page.keyboard.press("Escape")
        page.wait_for_timeout(600)
        after = overlay_state(page)
        run.note({f"overlay_{name}_closed_by_escape": not after.get("has_carousel"), "active_element": page.evaluate("document.activeElement && (document.activeElement.tagName + '#' + document.activeElement.id + '.' + document.activeElement.className).slice(0, 120)")})
        if after.get("has_carousel"):
            page.mouse.click(1200, 120)
            page.wait_for_timeout(600)
            after = overlay_state(page)
        run.check(f"overlay_{name}_closes", not after.get("has_carousel"), {"has_carousel": after.get("has_carousel")})


def g_de_edit(run: Run, page: Page):
    run.goto(page, "/de", "#de-main-box canvas")
    page.wait_for_timeout(3000)
    box = grid_canvas_box(page, "#de-main-box")
    # 1) first edit on a fresh page, typed fast (Glide lazily mounts its overlay editor)
    x, y = cell_xy(box, MAIN_W, 0, 7, 60, marker=32)
    page.mouse.click(x, y)
    page.wait_for_timeout(300)
    before = text(page, "#edits")
    page.keyboard.type("Zed")
    page.wait_for_timeout(800)
    page.keyboard.press("Enter")
    wait_text(page, "#edits", lambda s: s != before, timeout=6000)
    le = text(page, "#last-edit")
    try:
        got = json.loads(le)["cell"].get("data")
    except Exception:  # noqa: BLE001
        got = le
    run.check("first_edit_fast_typing_keeps_all_chars", got == "Zed", {"got": got})
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    def edit_cell(col, row, typed, label):
        x, y = cell_xy(box, MAIN_W, col, row, 60, marker=32)
        page.mouse.click(x, y)
        page.wait_for_timeout(300)
        before = text(page, "#edits")
        page.keyboard.press("Enter")
        page.wait_for_timeout(600)
        page.keyboard.press("ControlOrMeta+a")
        page.keyboard.type(typed, delay=60)
        page.wait_for_timeout(300)
        page.keyboard.press("Enter")
        t = wait_text(page, "#edits", lambda s: s != before, timeout=8000)
        le = text(page, "#last-edit")
        run.check(f"edit_{label}", t != before, {"edits": t, "last_edit": le})
        try:
            return json.loads(le)
        except Exception:  # noqa: BLE001
            return {"raw": le}

    d = edit_cell(0, 0, "Zed", "text")
    run.check("edit_text_payload", d.get("pos") == [0, 0] and d.get("cell", {}).get("data") == "Zed" and d.get("cell", {}).get("kind") == "text", d)
    d = edit_cell(1, 2, "42", "int")
    run.check("edit_int_payload", d.get("pos") == [1, 2] and d.get("cell", {}).get("data") == 42 and d.get("cell", {}).get("kind") == "number", d)
    d = edit_cell(2, 3, "9.5", "float")
    run.check("edit_float_payload", d.get("pos") == [2, 3] and d.get("cell", {}).get("data") == 9.5, d)
    d = edit_cell(10, 1, "2027-12-31", "datetime_as_text")
    run.check("edit_datetime_payload", d.get("cell", {}).get("data") == "2027-12-31", d)
    # bool: a single click on the checkbox toggles
    before = text(page, "#edits")
    x, y = cell_xy(box, MAIN_W, 3, 0, 60, marker=32)
    page.mouse.click(x, y)
    t = wait_text(page, "#edits", lambda s: s != before, timeout=5000)
    le = text(page, "#last-edit")
    run.check("edit_bool_single_click_toggles", t != before and '"kind": "boolean"' in le and '"data": false' in le, {"edits": t, "last_edit": le})
    page.wait_for_timeout(1000)
    before = text(page, "#edits")
    page.mouse.click(x, y)
    page.wait_for_timeout(1500)
    run.note({"bool_second_click_on_selected_cell": {"edits_before": before, "edits_after": text(page, "#edits"), "last_edit": text(page, "#last-edit")}})
    # read-only column: typing must not edit
    before = text(page, "#edits")
    x, y = cell_xy(box, MAIN_W, 11, 1, 60, marker=32)
    page.mouse.click(x, y)
    page.keyboard.type("nope", delay=40)
    page.keyboard.press("Enter")
    page.wait_for_timeout(1500)
    run.check("readonly_column_not_editable", text(page, "#edits") == before, text(page, "#edits"))
    page.keyboard.press("Escape")
    g = grid_cells(page, "#de-main-box")
    run.group["grid_cells_after_edit"] = g
    cells = g.get("cells", {})
    run.check("edited_values_visible_in_grid", cells.get("0-0", {}).get("data") == "Zed" and cells.get("1-2", {}).get("data") == 42 and cells.get("2-3", {}).get("data") == 9.5, {k: cells.get(k) for k in ("0-0", "1-2", "2-3", "3-0", "10-1")})
    # activation via double click
    x, y = cell_xy(box, MAIN_W, 0, 6, 60, marker=32)
    page.mouse.dblclick(x, y)
    t = wait_text(page, "#last-activated", lambda s: "0,6" in s, timeout=5000)
    run.check("on_cell_activated_dblclick", "0,6" in (t or ""), t)
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    run.shot(page, "de-after-edits", full=True)
    # Delete key with on_delete bound (last: it may break the grid)
    x, y = cell_xy(box, MAIN_W, 0, 5, 60, marker=32)
    page.mouse.click(x, y)
    page.wait_for_timeout(300)
    before = text(page, "#edits")
    n_err = len(run.group["pageerrors"])
    page.keyboard.press("Delete")
    page.wait_for_timeout(1500)
    run.group["after_delete"] = {"deleted": text(page, "#deleted")[:300], "edits_before": before, "edits_after": text(page, "#edits"), "last_edit": text(page, "#last-edit")[:200], "new_pageerrors": run.group["pageerrors"][n_err:]}
    run.check("on_delete_handler_receives_selection", '"cell": [0, 5]' in text(page, "#deleted"), run.group["after_delete"]["deleted"])
    run.check("delete_key_with_on_delete_no_pageerror", len(run.group["pageerrors"]) == n_err, run.group["after_delete"])
    run.check("delete_key_clears_cell_via_on_cell_edited", text(page, "#edits") != before, run.group["after_delete"])


def grid_bg(run: Run, page: Page, box_sel: str, name: str, rel=(0.5, 0.9)):
    el = page.locator(box_sel)
    p = run.out / "shots" / f"{run.label}-{name}.png"
    el.screenshot(path=str(p))
    img = pngutil.decode(p.read_bytes())
    w, h = img[0], img[1]
    return pngutil.pixel(img, int(w * rel[0]), int(h * rel[1]))


def g_de_theme(run: Run, page: Page):
    run.goto(page, "/de", "#de-main-box canvas")
    page.wait_for_timeout(3000)
    # sample a pixel inside the RO column of the last row (plain text cell background)
    rel = ((32 + sum(MAIN_W[:11]) + 52) / 1100, (36 + 7 * 60 + 8) / 560)
    light = grid_bg(run, page, "#de-main-box", "theme-light", rel)
    static = grid_bg(run, page, "#de-static-box canvas[data-testid=data-grid-canvas]", "theme-static", (0.8, 0.85))
    page.click("#toggle-theme")
    page.wait_for_timeout(1500)
    dark = grid_bg(run, page, "#de-main-box", "theme-dark", rel)
    run.check("state_theme_light_bg_is_light", sum(light) > 600, light)
    run.check("state_theme_dark_bg_matches_bgCell", abs(dark[0] - 0x16) < 12 and abs(dark[1] - 0x16) < 12 and abs(dark[2] - 0x1B) < 12, dark)
    run.check("static_DataEditorTheme_applied", sum(static) < 200, static)
    page.click("#toggle-theme")
    page.wait_for_timeout(1500)
    back = grid_bg(run, page, "#de-main-box", "theme-back", rel)
    run.check("state_theme_toggles_back", sum(back) > 600, back)


def g_de_resize_sort(run: Run, page: Page):
    run.goto(page, "/de", "#de-main-box canvas")
    page.wait_for_timeout(3000)
    box = grid_canvas_box(page, "#de-main-box")
    # header click on col 1 (Qty) -> handler sorts
    x = box["x"] + 32 + MAIN_W[0] + MAIN_W[1] / 2
    y = box["y"] + 18
    page.mouse.click(x, y)
    t = wait_text(page, "#header-clicks", lambda s: s.strip().endswith("1"), timeout=6000)
    logs = page.locator(".log-line").all_inner_texts()
    run.check("on_header_clicked_fires", (t or "").strip().endswith("1"), {"header_clicks": t, "log": logs[-3:]})
    g = grid_cells(page, "#de-main-box")
    run.note({"after_header_sort_qty_col": cell_values(g, 1)})
    # resize Name column by dragging its right edge
    ex = box["x"] + 32 + MAIN_W[0] - 2
    page.mouse.move(ex, y)
    page.mouse.down()
    page.mouse.move(ex + 20, y, steps=5)
    page.mouse.move(ex + 40, y, steps=5)
    page.mouse.up()
    t = wait_text(page, "#resize-log", lambda s: "name=" in s, timeout=6000)
    run.check("on_column_resize_updates_width", "name=" in (t or ""), t)
    run.shot(page, "de-after-resize", clip={"x": box["x"], "y": box["y"], "width": box["width"], "height": 200})


def g_de_multi(run: Run, page: Page):
    run.goto(page, "/de-multi", "#csa-box canvas")
    page.wait_for_timeout(3000)
    run.shot(page, "de-multi-initial", full=True)
    for p in ("csa", "csb"):
        run.check(f"{p}_canvas_present", page.locator(f"#{p}-box canvas").count() >= 1, page.locator(f"#{p}-box canvas").count())
    box = grid_canvas_box(page, "#csa-box")
    w = [150, 150]
    # default column widths unknown -> use a11y-independent coordinate near the left
    page.mouse.click(box["x"] + 20, box["y"] + 36 + 34 * 1 + 17)
    t = wait_text(page, "#csa-status", lambda s: "clicks 1" in s, timeout=6000)
    run.check("cs_a_click_updates_only_a", "clicks 1" in (t or "") and "clicks 0" in text(page, "#csb-status"), {"a": t, "b": text(page, "#csb-status")})
    # edit in csb
    boxb = grid_canvas_box(page, "#csb-box")
    page.mouse.click(boxb["x"] + 20, boxb["y"] + 36 + 17)
    page.wait_for_timeout(300)
    page.keyboard.press("Enter")
    page.wait_for_timeout(800)
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("zz", delay=60)
    page.keyboard.press("Enter")
    t = wait_text(page, "#csb-status", lambda s: "edits 1" in s, timeout=6000)
    run.check("cs_b_edit_isolated", "edits 1" in (t or "") and "edits 0" in text(page, "#csa-status") and '"zz"' in text(page, "#csb-rows") and '"zz"' not in text(page, "#csa-rows"), {"b": t, "b_rows": text(page, "#csb-rows"), "a_rows": text(page, "#csa-rows")})
    # memo editor add row
    cells_before = grid_cells(page, "#memo-box")
    page.click("#memo-add")
    t = wait_text(page, "#memo-title", lambda s: "(3)" in s, timeout=6000)
    page.wait_for_timeout(800)
    cells_after = grid_cells(page, "#memo-box")
    run.check("memo_editor_title_updates", "(3)" in (t or ""), t)
    run.check("memo_editor_rows_grow", cells_before.get("rows") == 2 and cells_after.get("rows") == 3 and "m3" in cell_values(cells_after, 0), {"before": cells_before.get("rows"), "after": cells_after.get("rows"), "col0": cell_values(cells_after, 0)})
    # dropdown grid
    if page.locator("#err-dropdown").count():
        run.check("dropdown_grid_constructs", False, text(page, "#err-dropdown"))
    else:
        run.check("dropdown_grid_renders_canvas", page.locator("#dd-box canvas").count() >= 1, None)
        ddc = grid_cells(page, "#dd-box")
        run.note({"dropdown_cells": ddc.get("cells") if isinstance(ddc, dict) else ddc})
    run.shot(page, "de-multi-after", full=True)


def g_de_filter(run: Run, page: Page):
    run.goto(page, "/de-filter", "#de-filter-box canvas")
    page.wait_for_timeout(3000)
    c0 = text(page, "#de-filter-count")
    run.check("filter_initial_all_rows", "30" in c0, c0)
    page.fill("#de-filter-input", "veg")
    t = wait_text(page, "#de-filter-count", lambda s: "10" in s and "30" not in s, timeout=6000)
    run.check("client_state_filter_reduces_rows", "10" in (t or ""), t)
    g = grid_cells(page, "#de-filter-box")
    vals = cell_values(g, 1)
    run.check("filtered_grid_shows_only_veg", g.get("rows") == 10 and vals and all(v == "veg" for v in vals), {"rows": g.get("rows"), "cat_col": vals[:12], "err": g.get("err")})
    page.click("#add-product")
    page.wait_for_timeout(1000)
    page.fill("#de-filter-input", "fruit")
    t = wait_text(page, "#de-filter-count", lambda s: "11" in s, timeout=6000)
    run.check("filter_tracks_backend_updates", "11" in (t or ""), t)
    mc = grid_cells(page, "#de-mapped-box")
    run.check("mapped_rows_grid_renders", mc.get("rows") == 31 and cell_values(mc, 0)[:1] == ["P00"], {"rows": mc.get("rows"), "col0": cell_values(mc, 0)[:5], "err": mc.get("err")})
    run.shot(page, "de-filter", full=True)


def g_de_foreach(run: Run, page: Page):
    page.goto(run.base + "/de-foreach", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(9000)
    if page.locator("#err-de-foreach").count():
        run.check("foreach_editors_construct", False, text(page, "#err-de-foreach"))
        return
    n = page.locator("#de-foreach .foreach-grid-box").count()
    nc = page.locator("#de-foreach canvas[data-testid=data-grid-canvas]").count()
    fc = [grid_cells(page, f"#de-foreach .foreach-grid-box:nth-child({i + 1})") for i in range(n)]
    fc = [{"rows": x.get("rows"), "col0": cell_values(x, 0), "err": x.get("err")} for x in fc]
    run.check("foreach_editors_render_without_errors", n == 2 and nc >= 2 and not run.group["pageerrors"] and not [c for c in run.group["console"] if c["type"] == "error"], {"boxes": n, "canvases": nc, "cells": fc, "pageerrors": run.group["pageerrors"][:2], "console_errors": [c["text"][:300] for c in run.group["console"] if c["type"] == "error"][:2]})
    run.shot(page, "de-foreach", full=True)


def g_de_big(run: Run, page: Page):
    page.add_init_script("""
      window.__longtasks = [];
      try { new PerformanceObserver(l => { for (const e of l.getEntries()) window.__longtasks.push(e.duration); }).observe({type: 'longtask', buffered: true}); } catch (e) {}
    """)
    t0 = time.time()
    run.goto(page, "/de-big", "#de-big-box canvas")
    t = wait_text(page, "#big-count", lambda s: "5000" in s, timeout=30000)
    load_s = round(time.time() - t0, 2)
    run.check("big_rows_loaded", "5000" in (t or ""), {"text": t, "seconds_to_5000": load_s})
    page.wait_for_timeout(2500)
    box = grid_canvas_box(page, "#de-big-box")
    run.note({"big_canvas_box": box})
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.evaluate("window.__longtasks = []")
    t1 = time.time()
    for _ in range(40):
        page.mouse.wheel(0, 800)
        page.wait_for_timeout(50)
    scroll_s = round(time.time() - t1, 2)
    page.wait_for_timeout(800)
    lt = page.evaluate("window.__longtasks")
    st = page.evaluate("(() => { const s = document.querySelector('#de-big-box .dvn-scroller'); return s ? [s.scrollTop, s.scrollHeight] : null; })()")
    run.check("big_scroll_moves", bool(st and st[0] > 20000), {"scroll": st, "wheel_seconds": scroll_s})
    run.check("big_scroll_no_long_tasks_over_250ms", all(d < 250 for d in (lt or [])), {"n_longtasks": len(lt or []), "max_ms": max(lt) if lt else 0, "sum_ms": round(sum(lt or []), 1)})
    page.evaluate("(() => { const s = document.querySelector('#de-big-box .dvn-scroller'); if (s) s.scrollTop = s.scrollHeight; })()")
    page.wait_for_timeout(800)
    page.mouse.click(box["x"] + 100, box["y"] + box["height"] - 30)
    t = wait_text(page, "#big-click", lambda s: re.search(r"\d+,49\d\d", s) is not None, timeout=6000)
    run.check("big_click_near_end_reports_row", bool(t and re.search(r"\d+,49\d\d", t)), t)
    run.shot(page, "de-big-end", full=False)


def g_nav(run: Run, page: Page):
    run.goto(page, "/de", "#de-main-box canvas")
    page.wait_for_timeout(2000)
    seq = ["de-multi", "de-filter", "dataeditor", "de-big", "forms", "dataeditor", "plotly", "de-multi"]
    routes = {"de-multi": "/de-multi", "de-filter": "/de-filter", "dataeditor": "/de", "de-big": "/de-big", "forms": "/forms", "plotly": "/plotly"}
    for label in seq:
        page.click(f"#nav-{label}")
        try:
            page.wait_for_url(f"**{routes[label]}", timeout=20000)
        except Exception as e:  # noqa: BLE001
            run.note(f"nav to {label} did not complete: {e!r}"[:200])
        page.wait_for_timeout(2000)
        run.note(f"navigated to {label}: url={page.url} canvases={page.locator('canvas').count()}")
        run.check(f"nav_{label}_url", page.url.rstrip("/").endswith(routes[label]), page.url)
    run.check("client_nav_between_editor_pages_no_pageerrors", len(run.group["pageerrors"]) == 0, run.group["pageerrors"][:3])


def g_forms(run: Run, page: Page):
    run.goto(page, "/forms", "#f_submit")
    page.wait_for_timeout(2500)
    page.click("#f_submit")
    t = wait_text(page, "#main_count", lambda s: s.strip() == "1", timeout=8000)
    p1 = text(page, "#main_payload")
    run.group["payload_unset"] = p1
    try:
        d = json.loads(p1)
    except Exception:  # noqa: BLE001
        d = {}
    run.check("unset_submit_received", t.strip() == "1" and bool(d), {"count": t, "payload": p1})
    stray = [k for k in ("main_form", "f_wrapper", "f_label", "f_submit", "f_notcontrol", "f_upload", "f_grid", "open_dialog", "d_close", "dialog_form", "d_submit") if k in d]
    run.check("no_stray_noncontrol_keys", not stray, {"stray": stray, "keys": sorted(d)})
    expected_present = ["f_text", "f_native", "f_slider", "f_check", "f_check_on", "f_switch", "f_radio", "f_select", "f_textarea", "f_debounced", "f_native_select", "f_rating", "f_named"]
    missing = [k for k in expected_present if k not in d]
    run.check("id_backed_controls_present_when_unset", not missing, {"missing": missing})
    run.note({"unset_values": {k: d.get(k, "<absent>") for k in sorted(set(d) | set(expected_present))}})
    # fill and submit
    page.fill("#f_text", "hello")
    page.fill("#f_native", "nat")
    page.click("#f_check")
    page.click("#f_switch")
    page.locator("#f_radio").get_by_text("y", exact=True).click()
    page.click("#f_select")
    page.get_by_role("option", name="s2").click()
    page.fill("#f_textarea", "multi\nline")
    page.fill("#f_debounced", "deb")
    page.select_option("#f_native_select", "n2")
    page.click("#rating3")
    page.wait_for_timeout(1200)
    page.click("#f_submit")
    t = wait_text(page, "#main_count", lambda s: s.strip() == "2", timeout=8000)
    p2 = text(page, "#main_payload")
    run.group["payload_filled"] = p2
    try:
        d2 = json.loads(p2)
    except Exception:  # noqa: BLE001
        d2 = {}
    exp = {"f_text": "hello", "f_native": "nat", "f_check": True, "f_switch": True, "f_radio": "y", "f_select": "s2", "f_textarea": "multi\nline", "f_debounced": "deb", "f_native_select": "n2", "f_rating": "3", "rating_native": "3", "f_named": "abc", "f_check_on": True}
    diff = {k: (d2.get(k, "<absent>"), v) for k, v in exp.items() if d2.get(k, "<absent>") != v}
    run.check("filled_payload_values", not diff, {"diff(got,exp)": diff, "slider": d2.get("f_slider")})
    stray2 = [k for k in ("main_form", "f_wrapper", "f_label", "f_submit", "f_notcontrol", "f_upload", "f_grid") if k in d2]
    run.check("filled_no_stray_keys", not stray2, stray2)
    # nested form in dialog
    before_main = text(page, "#main_count")
    page.click("#open_dialog")
    page.wait_for_selector("#d_text", timeout=8000)
    page.fill("#d_text", "dlg")
    page.click("#d_check")
    page.click("#d_submit")
    page.wait_for_timeout(2000)
    dc = text(page, "#dialog_count")
    dp = text(page, "#dialog_payload")
    mc = text(page, "#main_count")
    run.group["dialog"] = {"dialog_count": dc, "dialog_payload": dp, "main_count_before": before_main, "main_count_after": mc, "main_payload_after": text(page, "#main_payload")}
    try:
        dd = json.loads(dp)
    except Exception:  # noqa: BLE001
        dd = {}
    run.check("dialog_form_payload", dc.strip() == "1" and dd.get("d_text") == "dlg" and dd.get("d_check") is True and "dialog_form" not in dd, run.group["dialog"])
    run.check("dialog_submit_does_not_trigger_outer_form", mc == before_main, run.group["dialog"])
    run.shot(page, "forms-dialog")
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    # ComponentState forms
    page.fill("#csf1_text", "one")
    page.click("#csf1_go")
    page.click("#csf2_sw")
    page.click("#csf2_go")
    page.wait_for_timeout(2000)
    c1, c2 = text(page, "#csf1_payload"), text(page, "#csf2_payload")
    run.group["cs_forms"] = {"csf1": c1, "csf2": c2}
    ok1 = '"csf1_text": "one"' in c1 and "csf2" not in c1 and "csf1_label" not in c1 and "csf1_wrap" not in c1 and "csf1_form" not in c1
    ok2 = '"csf2_sw": true' in c2 and "csf1" not in c2 and "csf2_label" not in c2
    run.check("component_state_forms_isolated_and_clean", ok1 and ok2, run.group["cs_forms"])
    run.shot(page, "forms-final", full=True)


def g_match(run: Run, page: Page):
    run.goto(page, "/match", "#page-cycle")
    page.wait_for_timeout(2500)

    def snap():
        out = {}
        for sel in ("#top-comp", "#top-lit", "#memo-prop", "#memo-state", "#memo-foreach", "#mcs1-comp", "#mcs1-lit", "#mcs2-comp", "#mcs2-lit"):
            try:
                out[sel] = page.locator(sel).first.inner_text(timeout=3000).replace("\n", " | ")
            except Exception as e:  # noqa: BLE001
                out[sel] = f"<{type(e).__name__}>"
        return out

    s0 = snap()
    run.group["snap_a"] = s0
    exp0 = {"#top-comp": "top-A", "#top-lit": "toplit-a", "#memo-prop": "memoprop-A t1", "#memo-state": "memostate-A t2", "#memo-foreach": "memoprop-A f1", "#mcs1-comp": "A:p", "#mcs1-lit": "lit-a/p", "#mcs2-comp": "A:p"}
    bad0 = {k: s0.get(k) for k, v in exp0.items() if v not in (s0.get(k) or "")}
    run.check("match_initial_mode_a", not bad0 and not run.group["pageerrors"], {"bad": bad0, "pageerrors": run.group["pageerrors"][:2]})
    page.click("#page-cycle")
    page.wait_for_timeout(1200)
    s1 = snap()
    run.group["snap_b"] = s1
    exp1 = {"#top-comp": "top-B", "#top-lit": "toplit-d", "#memo-prop": "memoprop-B t1", "#memo-state": "memostate-B t2", "#memo-foreach": "memoprop-B f2"}
    bad1 = {k: s1.get(k) for k, v in exp1.items() if v not in (s1.get(k) or "")}
    run.check("match_page_cycle_to_b", not bad1, bad1)
    run.check("cs_match_unaffected_by_page_cycle", "A:p" in s1.get("#mcs1-comp", ""), s1.get("#mcs1-comp"))
    page.click("#mcs1-cycle")
    page.wait_for_timeout(1200)
    s2 = snap()
    run.group["snap_cs1_b"] = s2
    run.check("cs1_cycle_b_component_branch", "B:p" in s2.get("#mcs1-comp", "") and "B:q" in s2.get("#mcs1-comp", ""), s2.get("#mcs1-comp"))
    run.check("cs1_cycle_b_literal_branch", "lit-b/p" in s2.get("#mcs1-lit", ""), s2.get("#mcs1-lit"))
    run.check("cs2_isolated", "A:p" in s2.get("#mcs2-comp", "") and "lit-a/p" in s2.get("#mcs2-lit", ""), {"comp": s2.get("#mcs2-comp"), "lit": s2.get("#mcs2-lit")})
    page.click("#mcs1-cycle")
    page.click("#page-cycle")
    page.wait_for_timeout(1200)
    s3 = snap()
    run.group["snap_c"] = s3
    run.check("default_branches", "top-D" in s3.get("#top-comp", "") and "D:p" in s3.get("#mcs1-comp", "") and "lit-d/p" in s3.get("#mcs1-lit", "") and "memoprop-D t1" in s3.get("#memo-prop", ""), s3)
    run.shot(page, "match", full=True)


FIBER_JS = """
() => {
  const rootEl = document.getElementById('root') || document.body;
  let key = null, host = null;
  for (const el of [rootEl, ...rootEl.querySelectorAll('*')].slice(0, 50)) {
    key = Object.keys(el).find(k => k.startsWith('__reactContainer$') || k.startsWith('__reactFiber$'));
    if (key) { host = el; break; }
  }
  if (!key) return {err: 'no fiber key'};
  let fiber = host[key];
  if (key.startsWith('__reactContainer$')) fiber = fiber.stateNode ? fiber : fiber;
  while (fiber.return) fiber = fiber.return;
  const names = [];
  const stack = [fiber];
  let n = 0;
  while (stack.length && n < 200000) {
    const f = stack.pop(); n++;
    const t = f.type;
    if (t && typeof t !== 'string') {
      let nm = t.displayName || t.name;
      if (!nm && t.type) nm = 'memo(' + (t.type.displayName || t.type.name || '?') + ')';
      if (!nm && t.render) nm = 'forwardRef(' + (t.render.displayName || t.render.name || '?') + ')';
      if (nm) names.push(nm);
    }
    if (f.sibling) stack.push(f.sibling);
    if (f.child) stack.push(f.child);
  }
  return {count: n, names};
}
"""


def g_memo_names(run: Run, page: Page):
    run.goto(page, "/memo-names", "#memo-inc")
    page.wait_for_timeout(2000)
    page.click("#memo-inc")
    page.wait_for_timeout(1000)
    vals = page.locator(".memo-card .card-value").all_inner_texts()
    titles = page.locator(".memo-card .card-title").all_inner_texts()
    run.check("memo_cards_render_and_update", len(titles) == 6 and vals.count("1") >= 4, {"titles": titles, "values": vals})
    r = page.evaluate(FIBER_JS)
    names = r.get("names", [])
    cardish = sorted({n for n in names if "card" in n.lower() or n.lower().startswith("memo")})
    run.group["fiber_names_cardish"] = cardish
    run.group["fiber_count"] = r.get("count")
    dup = []
    for n in cardish:
        toks = re.findall(r"card_[0-9a-f]{6,}", n, flags=re.I)
        if len(toks) != len(set(t.lower() for t in toks)):
            dup.append(n)
    run.check("no_doubled_tag_in_memo_wrapper_names", not dup, {"doubled": dup, "cardish": cardish[:40]})


def plot_title(page: Page, pid: str, timeout=30000):
    try:
        page.wait_for_selector(f"#{pid} .gtitle", timeout=timeout)
        return page.locator(f"#{pid} .gtitle").first.text_content(timeout=3000)
    except Exception as e:  # noqa: BLE001
        return f"<{type(e).__name__}>"


def g_plotly(run: Run, page: Page):
    run.goto(page, "/plotly", "#plot-bump")
    page.wait_for_selector("#p_str .main-svg", timeout=90000)
    page.wait_for_timeout(2500)
    exp = {"p_str": "Literal string title", "p_obj": "Literal object title", "p_state_str": "State title 1", "p_state_dict": "Dict state title 1", "p_cond": "Cond title", "p_shared1": "Shared title", "p_shared2": "Shared title", "p_fig_str": "Fig string title", "p_fig_obj": "Fig object title", "p_fig_override": "Override title", "p_state_fig": "State fig title 1"}
    got = {k: plot_title(page, k, 10000) for k in exp}
    run.group["titles_initial"] = got
    for k, v in exp.items():
        run.check(f"title_{k}", got[k] == v, {"got": got[k], "exp": v})
    fill = page.evaluate("(() => { const t = document.querySelector('#p_obj .gtitle'); return t ? getComputedStyle(t).fill || t.style.fill : null; })()")
    run.check("object_title_font_color_red", fill is not None and ("255, 0, 0" in fill or "red" in fill), fill)
    run.shot(page, "plotly-initial", full=True)
    page.click("#plot-bump")
    page.wait_for_timeout(2500)
    exp2 = {"p_state_str": "State title 2", "p_state_dict": "Dict state title 2", "p_state_fig": "State fig title 2"}
    got2 = {k: plot_title(page, k, 10000) for k in exp2}
    for k, v in exp2.items():
        run.check(f"title_after_bump_{k}", got2[k] == v, {"got": got2[k], "exp": v})
    page.click("#plot-toggle")
    page.wait_for_timeout(1500)
    run.check("cond_plot_unmounted", page.locator("#p_cond").count() == 0, page.locator("#p_cond").count())
    page.click("#plot-toggle")
    t = plot_title(page, "p_cond", 20000)
    run.check("cond_plot_remounted_with_title", t == "Cond title", t)
    for _ in range(3):
        page.click("#plot-toggle")
        page.wait_for_timeout(400)
    page.wait_for_timeout(1500)
    run.shot(page, "plotly-after", full=True)


def axis_ticks(page: Page, cid: str, axis="xAxis"):
    return page.locator(f"#{cid} .recharts-{axis} .recharts-cartesian-axis-tick-value").all_text_contents()


def cdp_metrics(cdp):
    m = cdp.send("Performance.getMetrics")["metrics"]
    d = {x["name"]: x["value"] for x in m}
    return {k: d.get(k) for k in ("JSEventListeners", "Nodes", "JSHeapUsedSize", "Documents", "Frames", "LayoutCount", "RecalcStyleCount")}


def g_recharts(run: Run, page: Page):
    run.goto(page, "/recharts", "#rc-run")
    page.wait_for_timeout(3000)
    ids = ["rc_literal", "rc_var_create", "rc_funcstr", "rc_partial", "rc_args", "rc_untyped", "rc_memo"]
    ticks = {}
    for cid in ids:
        if page.locator(f"#err-{cid}").count():
            ticks[cid] = "ERR: " + text(page, f"#err-{cid}")[:200]
        else:
            ticks[cid] = axis_ticks(page, cid)[:3]
    run.group["ticks_initial"] = ticks
    exp = {"rc_literal": "L0", "rc_var_create": "A0", "rc_funcstr": "0u", "rc_partial": "$0", "rc_args": "$0", "rc_untyped": "R0", "rc_memo": "$0"}
    for cid, first in exp.items():
        v = ticks[cid]
        run.check(f"ticks_{cid}", isinstance(v, list) and bool(v) and v[0] == first, v)
    ytp = axis_ticks(page, "rc_partial", "yAxis")[:3] if not page.locator("#err-rc_partial").count() else None
    run.check("ticks_rc_partial_yaxis", bool(ytp) and ytp[0].startswith("$"), ytp)
    page.click("#rc-currency")
    page.wait_for_timeout(1200)
    t2 = {cid: (axis_ticks(page, cid)[:2] if not page.locator(f"#err-{cid}").count() else "ERR") for cid in ("rc_partial", "rc_args", "rc_memo")}
    run.group["ticks_after_currency"] = t2
    for cid, v in t2.items():
        run.check(f"ticks_after_currency_{cid}", isinstance(v, list) and bool(v) and v[0].startswith("EUR"), v)
    cdp = page.context.new_cdp_session(page)
    cdp.send("Performance.enable")
    page.evaluate("() => { if (window.gc) window.gc(); }")
    m0 = cdp_metrics(cdp)
    ys0 = axis_ticks(page, "rc_literal", "yAxis")
    path0 = page.evaluate("(() => { const p = document.querySelector('#rc_literal .recharts-line-curve'); return p ? p.getAttribute('d') : null; })()")
    page.click("#rc-run")
    samples = []
    for i in range(12):
        page.wait_for_timeout(1000)
        samples.append({"t": i + 1, "ticks": text(page, "#rc-ticks"), **cdp_metrics(cdp)})
    page.wait_for_timeout(1000)
    m1 = cdp_metrics(cdp)
    path1 = page.evaluate("(() => { const p = document.querySelector('#rc_literal .recharts-line-curve'); return p ? p.getAttribute('d') : null; })()")
    run.group["perf_samples"] = samples
    run.group["perf_before_after"] = {"before": m0, "after": m1}
    run.check("bg_task_ran_20_updates", "20" in text(page, "#rc-ticks"), text(page, "#rc-ticks"))
    run.check("chart_data_changed", path0 != path1 and path1 is not None, {"changed": path0 != path1})
    run.check("listeners_not_leaking", (m1["JSEventListeners"] or 0) <= (m0["JSEventListeners"] or 0) * 1.2 + 50, {"before": m0["JSEventListeners"], "after": m1["JSEventListeners"]})
    run.check("dom_nodes_stable", (m1["Nodes"] or 0) <= (m0["Nodes"] or 0) * 1.2 + 200, {"before": m0["Nodes"], "after": m1["Nodes"]})
    run.note({"heap_before_after_MB": [round((m0["JSHeapUsedSize"] or 0) / 1e6, 1), round((m1["JSHeapUsedSize"] or 0) / 1e6, 1)], "yticks_before": ys0[:3]})
    run.shot(page, "recharts-after", full=True)


def g_radix(run: Run, page: Page):
    run.goto(page, "/radix", "#sl1-run")
    page.wait_for_timeout(2500)
    thumb = page.locator("#sl1-slider [role=slider]").first
    thumb.focus()
    seq = [("ArrowRight", 55), ("ArrowRight", 60), ("ArrowRight", 65), ("ArrowLeft", 60), ("End", 100), ("Home", 0), ("PageUp", None), ("ArrowUp", None)]
    log = []
    for key, expv in seq:
        page.keyboard.press(key)
        page.wait_for_timeout(500)
        aria = thumb.get_attribute("aria-valuenow")
        val = text(page, "#sl1-value")
        com = text(page, "#sl1-committed")
        log.append({"key": key, "aria": aria, "state": val, "committed": com})
        if expv is not None:
            run.check(f"slider_{key}_{expv}", aria == str(expv) and val.endswith(f"={expv}") and com.endswith(f"={expv}"), log[-1])
    run.group["slider_log"] = log
    counts = text(page, "#sl1-counts")
    run.check("slider_change_and_commit_counts_match_keypresses", counts == f"changes={len(seq)} commits={len(seq)}", counts)
    run.check("slider2_unaffected", text(page, "#sl2-value") == "value=50" and page.locator("#sl2-slider [role=slider]").first.get_attribute("aria-valuenow") == "50", text(page, "#sl2-value"))
    page.click("#sl1-run")
    vals = []
    for _ in range(14):
        page.wait_for_timeout(300)
        pb = page.locator("#sl1-progress").first
        vals.append((text(page, "#sl1-progress-text"), pb.get_attribute("aria-valuenow"), pb.get_attribute("data-state"), pb.get_attribute("style")))
    run.group["progress_samples"] = vals
    run.check("progress_reaches_100", vals[-1][0].endswith("=100"), vals[-1])
    run.check("progress_aria_valuenow_tracks_state", vals[-1][1] == "100", vals[-1])
    run.check("progress2_unaffected", text(page, "#sl2-progress-text") == "progress=0", text(page, "#sl2-progress-text"))
    run.shot(page, "radix", full=True)


def g_code(run: Run, page: Page):
    run.goto(page, "/code", "#code-switch")
    page.wait_for_timeout(4000)

    def shiki(sel):
        return page.evaluate(
            """(sel) => { const b = document.querySelector(sel); if (!b) return null; const pre = b.querySelector('pre');
               return {cls: pre ? pre.className : null, colored: b.querySelectorAll('span[style*=color]').length, text: b.innerText.slice(0, 120), highlighted_lines: b.querySelectorAll('.line.highlighted').length, html_len: b.innerHTML.length}; }""",
            sel,
        )

    s0 = shiki("#shiki-dyn")
    run.check("shiki_dynamic_initial_highlighted", bool(s0 and s0["colored"] > 0 and "github-light" in (s0["cls"] or "")), s0)
    page.click("#code-switch")
    page.wait_for_timeout(3000)
    s1 = shiki("#shiki-dyn")
    run.check("shiki_dynamic_theme_lang_switch", bool(s1 and s1["colored"] > 0 and "dracula" in (s1["cls"] or "") and "const" in (s1["text"] or "")), s1)
    st = shiki("#shiki-transformers")
    run.group["shiki_transformers"] = st
    run.note({"known_defect_use_transformers_highlighted_lines": st and st["highlighted_lines"]})
    sd = shiki("#shiki-themes-dict")
    run.check("shiki_themes_dict_highlighted", bool(sd and sd["colored"] > 0), sd)
    # parent re-render: does the themes-dict block flash back to plain text?
    page.evaluate("""() => { window.__shikiMut = 0; const b = document.querySelector('#shiki-themes-dict'); if (b) new MutationObserver(() => window.__shikiMut++).observe(b, {subtree: true, childList: true}); }""")
    for _ in range(3):
        page.click("#code-bump")
        page.wait_for_timeout(700)
    run.note({"shiki_themes_dict_mutations_after_3_parent_rerenders": page.evaluate("window.__shikiMut")})
    md = page.evaluate("""() => { const b = document.querySelector('#md-fenced'); return b ? {pres: b.querySelectorAll('pre').length, colored: b.querySelectorAll('span[style*=color], span[class*=token]').length, text: b.innerText.slice(0, 200)} : null; }""")
    run.check("markdown_fenced_code_rendered", bool(md and md["pres"] >= 2), md)
    m0 = text(page, "#m-state")
    run.check("moment_state_tz_locale_format", m0.strip() == "jeudi 15 janvier 2026 07:34", m0)
    page.click("#moment-switch")
    m1 = wait_text(page, "#m-state", lambda s: "JST" in s, timeout=5000)
    run.check("moment_state_switch", (m1 or "").strip() == "2026-01-15 21:34 JST", m1)
    a = text(page, "#m-tick")
    page.wait_for_timeout(2200)
    b = text(page, "#m-tick")
    run.check("moment_interval_ticks", a != b and re.match(r"\d\d:\d\d:\d\d", b or ""), {"a": a, "b": b})
    ch = text(page, "#m-changes")
    run.note({"moment_on_change_count_after_~10s": ch})
    run.check("moment_duration_format", text(page, "#m-duration").strip() == "01:30:15", text(page, "#m-duration"))
    run.check("moment_ja_locale", "2026" in text(page, "#m-ja") and "日" in text(page, "#m-ja"), text(page, "#m-ja"))
    run.shot(page, "code", full=True)


def _payload(n: int) -> str:
    unit = (
        "line #1 100% sure %41 %%25 ? & = + / \\ \" ' <tag> "
        "\U0001f600\U0001f469\u200d\U0001f4bb \u4e2d\u6587 \u00e9\u00e8 \u2028\u2029 "
        "\x01\x02\x1f\x7f\u0080\u00ff tab\tcr\rlf\n"
    )
    reps = n // len(unit) + 1
    return (unit * reps)[:n]


def g_download(run: Run, page: Page):
    run.goto(page, "/download", "#dl-var")
    page.wait_for_timeout(2000)
    dl_dir = run.out / "downloads"
    dl_dir.mkdir(exist_ok=True)

    def do(btn, fname, timeout=20000):
        try:
            with page.expect_download(timeout=timeout) as di:
                page.click(btn)
            d = di.value
            p = dl_dir / f"{run.label}-{fname}"
            d.save_as(str(p))
            return p.read_bytes(), d.suggested_filename, None
        except Exception as e:  # noqa: BLE001
            return None, None, f"{type(e).__name__}: {str(e)[:200]}"

    body, name, err = do("#dl-list", "list.json")
    exp_list = json.dumps([{"address": "12 Main St #4", "note": "100%25 sure", "emoji": "\U0001f600"}], separators=(",", ":"), ensure_ascii=False).encode()
    run.check("download_list_var_exact", body == exp_list, {"got": body[:200] if body else None, "exp": exp_list[:200], "err": err, "name": name})
    body, name, err = do("#dl-dataurl", "du.txt")
    run.check("download_dataurl_var_passthrough", body == b"already a data url #hash", {"got": body, "err": err})
    for n in (10_000, 500_000, 1_000_000, 2_000_000):
        page.click(f"#make-{n}")
        t = wait_text(page, "#dl-size", lambda s: s.strip() == f"size={n}", timeout=30000)
        if (t or "").strip() != f"size={n}":
            run.check(f"make_payload_{n}", False, t)
            continue
        s = _payload(n)
        exp_var = json.dumps(s, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        body, name, err = do("#dl-var", f"var-{n}.txt", timeout=30000)
        info = {"err": err, "got_len": len(body) if body else None, "exp_len": len(exp_var)}
        if body and body != exp_var:
            i = next((k for k in range(min(len(body), len(exp_var))) if body[k] != exp_var[k]), min(len(body), len(exp_var)))
            info["first_diff_at"] = i
            info["got_ctx"] = body[max(0, i - 20) : i + 20].decode("utf-8", "replace")
            info["exp_ctx"] = exp_var[max(0, i - 20) : i + 20].decode("utf-8", "replace")
            info["got_equals_raw_utf8"] = body == s.encode("utf-8")
        run.check(f"download_var_{n}_exact_json", body == exp_var, info)
        body, name, err = do("#dl-backend", f"backend-{n}.txt", timeout=30000)
        exp_raw = s.encode("utf-8")
        run.check(f"download_backend_str_{n}_exact_raw", body == exp_raw, {"err": err, "got_len": len(body) if body else None, "exp_len": len(exp_raw)})


GROUPS = {
    "de_main": g_de_main,
    "de_overlay": g_de_overlay,
    "de_edit": g_de_edit,
    "de_theme": g_de_theme,
    "de_resize_sort": g_de_resize_sort,
    "de_multi": g_de_multi,
    "de_filter": g_de_filter,
    "de_foreach": g_de_foreach,
    "de_big": g_de_big,
    "nav": g_nav,
    "forms": g_forms,
    "match": g_match,
    "memo_names": g_memo_names,
    "plotly": g_plotly,
    "recharts": g_recharts,
    "radix": g_radix,
    "code": g_code,
    "download": g_download,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("outdir")
    ap.add_argument("--groups", default=",".join(GROUPS))
    ap.add_argument("--label", default="run")
    a = ap.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    run = Run(a.base, out, a.label)
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    with sync_playwright() as p:
        kw = {"executable_path": CHROMIUM}
        if proxy:
            kw["proxy"] = {"server": proxy, "bypass": "localhost,127.0.0.1"}
        browser = p.chromium.launch(**kw)
        for g in a.groups.split(","):
            print(f"== group {g}", flush=True)
            run.start_group(g)
            ctx = browser.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True)
            page = ctx.new_page()
            run.attach(page)
            t0 = time.time()
            try:
                GROUPS[g](run, page)
            except Exception as e:  # noqa: BLE001
                run.check("group_exception", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}")
                try:
                    run.shot(page, f"{g}-exception", full=True)
                except Exception:  # noqa: BLE001
                    pass
            run.group["seconds"] = round(time.time() - t0, 1)
            errs = [c for c in run.group["console"] if c["type"] in ("error", "warning")]
            print(f"   console errors/warnings: {len(errs)}; pageerrors: {len(run.group['pageerrors'])}; failed req: {len(run.group['failed_requests'])}; http>=400: {len(run.group['http_errors'])}", flush=True)
            for c in errs[:6]:
                print(f"     {c['type']}: {c['text'][:220]}", flush=True)
            for e in run.group["pageerrors"][:3]:
                print(f"     pageerror: {e[:220]}", flush=True)
            ctx.close()
            (out / "results.json").write_text(json.dumps(run.results, indent=1, default=str))
        browser.close()
    fails = [(g, c["name"]) for g, gd in run.results["groups"].items() for c in gd["checks"] if not c["ok"]]
    print(f"TOTAL FAILS: {len(fails)}", fails, flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
