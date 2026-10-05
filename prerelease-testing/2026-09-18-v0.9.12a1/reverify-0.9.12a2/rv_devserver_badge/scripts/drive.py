"""Drive the 0.9.12a1 component gallery and dump observations as JSON.

Usage: driver-venv/bin/python drive.py <base_url> <out_dir> [phase]
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2])
PHASE = sys.argv[3] if len(sys.argv) > 3 else "dev"
OUT.mkdir(parents=True, exist_ok=True)

console: list[dict] = []
pageerrors: list[str] = []
failed: list[dict] = []
bad_responses: list[dict] = []
results: dict = {}


def attach(page):
    page.on(
        "console",
        lambda m: console.append({"type": m.type, "text": m.text, "url": page.url}),
    )
    page.on("pageerror", lambda e: pageerrors.append(f"{page.url}: {e}"))
    page.on(
        "requestfailed",
        lambda r: failed.append({"url": r.url, "err": str(r.failure)}),
    )

    def on_resp(r):
        if r.status >= 400:
            bad_responses.append({"url": r.url, "status": r.status})

    page.on("response", on_resp)


def shot(page, name):
    p = OUT / f"{PHASE}-{name}.png"
    page.screenshot(path=str(p), full_page=False)
    return str(p)


def goto(page, path):
    page.goto(f"{BASE}{path}", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(1200)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    try:
        ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    except Exception as e:  # noqa: BLE001
        results["clipboard_perm_error"] = str(e)
    page = ctx.new_page()
    attach(page)

    # ---------------------------------------------------------------- sankey
    goto(page, "/sankey")
    r = {}
    r["static_paths"] = page.locator("#sankey-static svg path").count()
    r["static_rects"] = page.locator("#sankey-static svg rect").count()
    r["stateful_rects"] = page.locator("#sankey-stateful svg rect").count()
    r["custom_texts"] = page.locator("#sankey-custom svg text").count()
    r["custom_gradients"] = page.locator("#sankey-custom svg linearGradient").count()
    grad_ids = page.eval_on_selector_all(
        "#sankey-custom svg linearGradient", "els => els.map(e => e.id)"
    )
    r["custom_gradient_ids"] = grad_ids
    r["custom_gradient_ids_unique"] = len(set(grad_ids)) == len(grad_ids)
    # do the paths reference the gradients?
    strokes = page.eval_on_selector_all(
        "#sankey-custom svg path", "els => els.map(e => e.getAttribute('stroke'))"
    )
    r["custom_path_strokes"] = strokes[:10]
    r["gradients_referenced"] = all(
        f"url(#{gid})" in strokes for gid in grad_ids
    ) if grad_ids else False
    # custom node label placement uses use_chart_width: rightmost label anchored end
    anchors = page.eval_on_selector_all(
        "#sankey-custom svg text", "els => els.map(e => e.getAttribute('text-anchor'))"
    )
    r["custom_text_anchors"] = anchors
    r["has_end_anchor"] = "end" in anchors
    r["foreach_charts"] = page.locator("#sankey-foreach svg").count()
    r["foreach_gradient_ids"] = page.eval_on_selector_all(
        "#sankey-foreach svg linearGradient", "els => els.map(e => e.id)"
    )
    r["width_outside"] = page.locator("#width-outside").inner_text()
    r["width_cond"] = page.locator("#width-cond").inner_text()
    shot(page, "sankey-initial")

    # stateful update
    before = page.eval_on_selector_all(
        "#sankey-stateful svg path", "els => els.map(e => e.getAttribute('stroke-width'))"
    )
    page.click("#btn-randomize")
    page.wait_for_timeout(1500)
    after = page.eval_on_selector_all(
        "#sankey-stateful svg path", "els => els.map(e => e.getAttribute('stroke-width'))"
    )
    r["stateful_widths_changed"] = before != after
    r["seed_text"] = page.locator("#sankey-seed").inner_text()
    page.click("#btn-addnode")
    page.wait_for_timeout(1500)
    r["stateful_rects_after_add"] = page.locator("#sankey-stateful svg rect").count()
    shot(page, "sankey-after-state")

    # resize viewport -> use_chart_width should re-evaluate label placement
    anchors_wide = page.eval_on_selector_all(
        "#sankey-custom svg text", "els => els.map(e => e.getAttribute('text-anchor'))"
    )
    xs_wide = page.eval_on_selector_all(
        "#sankey-custom svg text", "els => els.map(e => e.getAttribute('x'))"
    )
    page.set_viewport_size({"width": 520, "height": 900})
    page.wait_for_timeout(2000)
    anchors_narrow = page.eval_on_selector_all(
        "#sankey-custom svg text", "els => els.map(e => e.getAttribute('text-anchor'))"
    )
    xs_narrow = page.eval_on_selector_all(
        "#sankey-custom svg text", "els => els.map(e => e.getAttribute('x'))"
    )
    r["anchors_wide"] = anchors_wide
    r["anchors_narrow"] = anchors_narrow
    r["xs_wide"] = xs_wide[:8]
    r["xs_narrow"] = xs_narrow[:8]
    r["width_reacts_to_resize"] = xs_wide != xs_narrow
    shot(page, "sankey-narrow")
    page.set_viewport_size({"width": 1280, "height": 900})
    page.wait_for_timeout(800)
    results["sankey"] = r

    # ----------------------------------------------------------------- props
    goto(page, "/props")
    r = {}
    r["grid_dash"] = page.eval_on_selector_all(
        "#props-chart .recharts-cartesian-grid line",
        "els => els.map(e => e.getAttribute('stroke-dasharray')).slice(0,3)",
    )
    r["line_dash"] = page.eval_on_selector_all(
        "#props-chart .recharts-line-curve",
        "els => els.map(e => e.getAttribute('stroke-dasharray'))",
    )
    r["refline_dash"] = page.eval_on_selector_all(
        "#props-chart .recharts-reference-line line",
        "els => els.map(e => e.getAttribute('stroke-dasharray'))",
    )
    r["x_ticks"] = page.eval_on_selector_all(
        "#props-chart .recharts-xAxis .recharts-cartesian-axis-tick-value tspan",
        "els => els.map(e => e.textContent)",
    )
    r["y_ticks"] = page.eval_on_selector_all(
        "#props-chart .recharts-yAxis .recharts-cartesian-axis-tick-value tspan",
        "els => els.map(e => e.textContent)",
    )
    r["wrapper_style_attr"] = page.eval_on_selector(
        "#props-chart .recharts-responsive-container",
        "e => e.getAttribute('style')",
    )
    r["wrapper_inner_style"] = page.eval_on_selector_all(
        "#props-chart div", "els => els.map(e => e.getAttribute('style')).slice(0,6)"
    )
    shot(page, "props-initial")
    page.click("#btn-dash")
    page.wait_for_timeout(1200)
    r["refline_dash_after_toggle"] = page.eval_on_selector_all(
        "#props-chart .recharts-reference-line line",
        "els => els.map(e => e.getAttribute('stroke-dasharray'))",
    )
    r["dash_value"] = page.locator("#dash-value").inner_text()
    shot(page, "props-after-toggle")
    results["props"] = r

    # ---------------------------------------------------------------- editor
    goto(page, "/editor")
    r = {}
    page.wait_for_timeout(1500)
    r["canvas_count"] = page.locator("#editor-box canvas").count()
    r["memo_canvas_count"] = page.locator("#editor-memo canvas").count()
    # glide draws to canvas; check the carousel CSS is present
    r["carousel_css_in_dom"] = page.evaluate(
        """() => {
            const out = [];
            for (const sheet of Array.from(document.styleSheets)) {
                let rules;
                try { rules = sheet.cssRules; } catch (e) { continue; }
                for (const rule of Array.from(rules || [])) {
                    const t = rule.cssText || '';
                    if (t.includes('gdg-') || t.toLowerCase().includes('carousel')) out.push(t.slice(0,120));
                }
            }
            return out.slice(0, 12);
        }"""
    )
    shot(page, "editor-initial")
    # click image cell (row 0, col 0) then open overlay via keyboard/dblclick
    box = page.locator("#editor-box canvas").first.bounding_box()
    if box:
        page.mouse.click(box["x"] + 55, box["y"] + 60)
        page.wait_for_timeout(700)
        r["clicks_after_single"] = page.locator("#editor-clicks").inner_text()
        r["lastcell"] = page.locator("#editor-lastcell").inner_text()
        page.mouse.dblclick(box["x"] + 55, box["y"] + 60)
        page.wait_for_timeout(1500)
        shot(page, "editor-overlay")
        r["overlay_present"] = page.locator("div[class*='gdg-']").count()
        r["overlay_imgs"] = page.eval_on_selector_all(
            "img", "els => els.map(e => e.getAttribute('src')).slice(0,10)"
        )
        r["overlay_html_snippet"] = page.evaluate(
            """() => {
                const el = document.querySelector('.gdg-overlay-editor') ||
                           document.querySelector('[class*=gdg-o]') ||
                           document.querySelector('[class*=click-outside]');
                return el ? el.outerHTML.slice(0, 900) : null;
            }"""
        )
        page.keyboard.press("Escape")
        page.wait_for_timeout(400)
    page.click("#btn-addrow")
    page.wait_for_timeout(1200)
    r["clicks_final"] = page.locator("#editor-clicks").inner_text()
    shot(page, "editor-after-add")
    results["editor"] = r

    # ---------------------------------------------------------------- plotly
    goto(page, "/plotly")
    page.wait_for_timeout(2500)
    r = {}
    r["myplot_exists"] = page.evaluate("() => !!document.getElementById('myplot')")
    r["stateplot_exists"] = page.evaluate("() => !!document.getElementById('stateplot')")
    r["fe_one"] = page.evaluate("() => !!document.getElementById('fe-one')")
    r["fe_two"] = page.evaluate("() => !!document.getElementById('fe-two')")
    r["plotly_divs"] = page.eval_on_selector_all(
        ".js-plotly-plot", "els => els.map(e => e.id)"
    )
    r["svg_count"] = page.locator(".js-plotly-plot svg").count()
    shot(page, "plotly-initial")
    page.click("#btn-bump")
    page.wait_for_timeout(1800)
    r["n_after_bump"] = page.locator("#plotly-n").inner_text()
    r["stateplot_still_exists"] = page.evaluate(
        "() => !!document.getElementById('stateplot')"
    )
    r["stateplot_bar_heights"] = page.eval_on_selector_all(
        "#stateplot .point path", "els => els.map(e => e.getAttribute('d')).slice(0,3)"
    )
    shot(page, "plotly-after-bump")
    results["plotly"] = r

    # ----------------------------------------------------------------- toast
    goto(page, "/toast")
    r = {}

    def toast_click(btn_id, label, key):
        page.click(btn_id)
        page.wait_for_timeout(900)
        btn = page.locator(f"button:has-text('{label}')")
        r[f"{key}_button_visible"] = btn.count() > 0
        if btn.count():
            btn.first.click()
            page.wait_for_timeout(1200)
        r[f"{key}_action_hits"] = page.locator("#action-hits").inner_text()
        r[f"{key}_cancel_hits"] = page.locator("#cancel-hits").inner_text()

    toast_click("#btn-fe-toast", "FE-ACT", "fe_action")
    shot(page, "toast-fe")
    page.click("#btn-fe-toast")
    page.wait_for_timeout(900)
    can = page.locator("button:has-text('FE-CAN')")
    r["fe_cancel_visible"] = can.count() > 0
    if can.count():
        can.first.click()
        page.wait_for_timeout(1200)
    r["after_fe_cancel"] = page.locator("#cancel-hits").inner_text()

    toast_click("#btn-memo-toast", "M-ACT", "memo")
    toast_click("#btn-cs-toast", "CS-ACT", "cs")
    r["cs_local"] = page.locator("#cs-local").inner_text()
    toast_click("#btn-be-toast", "BE-ACT", "backend")
    toast_click("#btn-bg-toast", "BG-ACT", "bg")
    r["log"] = page.locator("#toast-log").inner_text()
    shot(page, "toast-final")
    # foreach-generated toast buttons exist now (log non-empty)
    fe_items = page.locator("button[id^='btn-item-']")
    r["foreach_buttons"] = fe_items.count()
    if fe_items.count():
        fe_items.first.click()
        page.wait_for_timeout(900)
        b = page.locator("button:has-text('FEACH-ACT')")
        r["foreach_action_visible"] = b.count() > 0
        if b.count():
            b.first.click()
            page.wait_for_timeout(1200)
        r["foreach_action_hits"] = page.locator("#action-hits").inner_text()
    page.click("#btn-fe-toast")
    page.wait_for_timeout(600)
    r["toasts_before_dismiss"] = page.locator("li[data-sonner-toast]").count()
    page.click("#btn-dismiss")
    page.wait_for_timeout(1200)
    r["toasts_after_dismiss"] = page.locator("li[data-sonner-toast]").count()
    shot(page, "toast-after-dismiss")
    results["toast"] = r

    # ------------------------------------------------------------------ code
    goto(page, "/code")
    r = {}
    copy_btns = page.locator("#code-in-form button")
    r["copy_btn_count"] = copy_btns.count()
    r["copy_btn_attrs"] = page.eval_on_selector_all(
        "#code-in-form button",
        "els => els.map(e => ({aria: e.getAttribute('aria-label'), type: e.getAttribute('type'), text: e.textContent}))",
    )
    r["submits_before"] = page.locator("#submit-count").inner_text()
    if copy_btns.count():
        copy_btns.first.click()
        page.wait_for_timeout(1200)
    r["submits_after_copy"] = page.locator("#submit-count").inner_text()
    try:
        r["clipboard"] = page.evaluate("() => navigator.clipboard.readText()")
    except Exception as e:  # noqa: BLE001
        r["clipboard_error"] = str(e)
    shot(page, "code-copy")
    page.click("#btn-submit")
    page.wait_for_timeout(1200)
    r["submits_after_submit"] = page.locator("#submit-count").inner_text()
    page.click("#btn-lang")
    page.wait_for_timeout(1500)
    r["lang"] = page.locator("#cur-lang").inner_text()
    r["dynamic_code_text"] = page.locator("#code-dynamic").inner_text()[:120]
    page.click("#btn-theme")
    page.wait_for_timeout(1500)
    r["dynamic_code_text_after_theme"] = page.locator("#code-dynamic").inner_text()[:120]
    shot(page, "code-dynamic")
    page.locator("#code-belowfold").scroll_into_view_if_needed()
    page.wait_for_timeout(1500)
    r["belowfold_text"] = page.locator("#code-belowfold").inner_text()[:120]
    r["belowfold_tokens"] = page.locator("#code-belowfold span").count()
    shot(page, "code-belowfold")
    results["code"] = r

    # ------------------------------------------------------------------ misc
    goto(page, "/misc")
    r = {}
    r["md_text"] = page.locator("#md-box").inner_text()[:220]
    r["md_table_rows"] = page.locator("#md-box table tr").count()
    r["md_code_blocks"] = page.locator("#md-box pre").count()
    r["table_rows"] = page.locator("#table-box tbody tr").count()
    page.click("#btn-tablerow")
    page.wait_for_timeout(1200)
    r["table_rows_after_add"] = page.locator("#table-box tbody tr").count()
    # search
    search = page.locator("#table-box input[type='search'], #table-box input")
    if search.count():
        search.first.fill("Engineer")
        page.wait_for_timeout(1000)
        r["table_rows_after_search"] = page.locator("#table-box tbody tr").count()
        search.first.fill("")
        page.wait_for_timeout(800)
    shot(page, "misc-table")
    # segmented control
    page.locator("#segctl button", has_text="Two").first.click()
    page.wait_for_timeout(1000)
    r["seg_value"] = page.locator("#seg-value").inner_text()
    page.locator("#segctl button", has_text="Three").first.click()
    page.wait_for_timeout(1000)
    r["seg_value2"] = page.locator("#seg-value").inner_text()
    # use_id in foreach
    ids = page.eval_on_selector_all(
        "#ids-box .foreach-input", "els => els.map(e => e.id)"
    )
    hfs = page.eval_on_selector_all(
        "#ids-box .foreach-label", "els => els.map(e => e.getAttribute('for'))"
    )
    r["foreach_ids"] = ids
    r["foreach_html_for"] = hfs
    r["foreach_ids_unique"] = len(set(ids)) == len(ids) and len(ids) > 0
    r["foreach_ids_match_labels"] = ids == hfs
    r["memo_hook_id"] = page.locator(".memo-hook-id").inner_text()
    r["memo_input_id"] = page.eval_on_selector(".memo-hook-input", "e => e.id")
    r["hookvar_text"] = page.locator("#hookvar-text").inner_text()
    r["hookvar_cond"] = page.locator("#hookvar-cond").inner_text()
    # stability across re-render
    page.click("#btn-tablerow")
    page.wait_for_timeout(1200)
    ids2 = page.eval_on_selector_all(
        "#ids-box .foreach-input", "els => els.map(e => e.id)"
    )
    r["foreach_ids_stable"] = ids == ids2
    r["foreach_ids_2"] = ids2
    shot(page, "misc-ids")
    # badge a11y at 360px
    page.set_viewport_size({"width": 360, "height": 800})
    page.wait_for_timeout(1000)
    r["badge_a11y"] = page.evaluate(
        """() => Array.from(document.querySelectorAll('a')).filter(
            a => (a.href||'').includes('reflex.dev')
        ).map(a => ({aria: a.getAttribute('aria-label'), text: a.textContent.trim(),
                     title: a.getAttribute('title')}))"""
    )
    shot(page, "misc-badge-360")
    page.set_viewport_size({"width": 1280, "height": 900})
    results["misc"] = r

    # client-side navigation round trip
    goto(page, "/")
    page.click("#nav-sankey")
    page.wait_for_timeout(2500)
    results["nav"] = {
        "url": page.url,
        "sankey_rects": page.locator("#sankey-static svg rect").count(),
    }
    page.click("#nav-code")
    page.wait_for_timeout(2000)
    results["nav"]["code_copy_btns"] = page.locator("#code-in-form button").count()
    page.click("#nav-plotly")
    page.wait_for_timeout(2500)
    results["nav"]["plotly_myplot"] = page.evaluate(
        "() => !!document.getElementById('myplot')"
    )
    shot(page, "nav-final")

    browser.close()

results["console"] = console
results["pageerrors"] = pageerrors
results["failed_requests"] = failed
results["bad_responses"] = bad_responses
(OUT / f"{PHASE}-results.json").write_text(json.dumps(results, indent=2, default=str))
print(json.dumps({k: v for k, v in results.items() if k != "console"}, indent=2, default=str))
print("\n--- console (errors/warnings) ---")
for m in console:
    if m["type"] in ("error", "warning"):
        print(m["type"], "|", m["text"][:300], "|", m["url"])
