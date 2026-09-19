"""Drive the reflex-examples `nba` app: gridjs data_table over a pandas
DataFrame (#7049 on-demand serializers), plotly scatter+histogram, and the
position/college/age/salary filters. Also checks that rx.plotly(id=...) reaches
the DOM as react-plotly's divId (#6977).

usage: drive_nba.py <frontend_url> <label> <shots_dir>
"""

import json
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1].rstrip("/")
LABEL = sys.argv[2]
SHOTS = sys.argv[3]

console, page_errors, failed, bad = [], [], [], []
r = {}


def plot_info(page):
    return page.evaluate(
        """() => {
            const plots = Array.from(document.querySelectorAll('.js-plotly-plot'));
            return plots.map(p => ({
                id: p.id,
                traces: (p.data || []).length,
                points: (p.data || []).reduce((n, t) => n + ((t.x && t.x.length) || 0), 0),
                title: (p.layout && p.layout.title && (p.layout.title.text || p.layout.title)) || null,
            }));
        }"""
    )


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = browser.new_context(viewport={"width": 1500, "height": 1100}).new_page()
    page.on("console", lambda m: console.append({"type": m.type, "text": m.text}))
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on("requestfailed", lambda q: failed.append(f"{q.method} {q.url} :: {q.failure}"))
    page.on("response", lambda x: bad.append(f"{x.status} {x.url}") if x.status >= 400 else None)

    page.goto(URL + "/", wait_until="networkidle", timeout=120_000)
    page.wait_for_timeout(6000)

    # gridjs data_table fed from a pandas DataFrame
    r["gridjs_present"] = page.locator(".gridjs-table").count() > 0
    r["grid_rows"] = page.locator(".gridjs-tbody tr").count()
    r["grid_headers"] = [
        h.inner_text() for h in page.locator(".gridjs-thead th").all()
    ][:12]
    r["search_box"] = page.locator(".gridjs-search-input").count() > 0

    # plotly charts
    pi = plot_info(page)
    r["plots"] = pi
    r["plot_count"] = len(pi)
    r["plot_ids"] = [x["id"] for x in pi]
    # #6977: id must land on the plot div as divId
    r["scatter_id_reached_dom"] = any(x["id"] == "scatter-chart" for x in pi)
    r["scatter_by_selector"] = page.locator("#scatter-chart").count()
    r["scatter_is_plotly"] = page.evaluate(
        "() => { const e=document.getElementById('scatter-chart');"
        " return !!(e && e.classList.contains('js-plotly-plot')); }"
    )
    page.screenshot(path=f"{SHOTS}/{LABEL}_01_initial.png", full_page=True)

    # filter by position -> both charts and the state recompute
    before = plot_info(page)
    sel = page.get_by_role("combobox").first
    sel.click()
    page.wait_for_timeout(800)
    page.get_by_role("option", name="PG", exact=True).click()
    page.wait_for_timeout(4000)
    after = plot_info(page)
    r["points_before_filter"] = before[0]["points"] if before else None
    r["points_after_pg_filter"] = after[0]["points"] if after else None
    r["filter_changed_plot"] = (
        bool(before) and bool(after) and before[0]["points"] != after[0]["points"]
    )
    r["id_survives_filter"] = any(x["id"] == "scatter-chart" for x in after)
    page.screenshot(path=f"{SHOTS}/{LABEL}_02_filter_pg.png", full_page=True)

    # gridjs search
    if r["search_box"]:
        page.locator(".gridjs-search-input").fill("Duke")
        page.wait_for_timeout(2500)
        r["grid_rows_after_search"] = page.locator(".gridjs-tbody tr").count()
        page.screenshot(path=f"{SHOTS}/{LABEL}_03_search.png", full_page=True)
        page.locator(".gridjs-search-input").fill("")
        page.wait_for_timeout(1500)

    # gridjs pagination
    nxt = page.locator(".gridjs-pagination button", has_text="Next")
    if nxt.count():
        first_cell_before = page.locator(".gridjs-tbody tr td").first.inner_text()
        nxt.first.click()
        page.wait_for_timeout(2000)
        r["pagination_changed_rows"] = (
            page.locator(".gridjs-tbody tr td").first.inner_text() != first_cell_before
        )
        page.screenshot(path=f"{SHOTS}/{LABEL}_04_page2.png", full_page=True)

    # reload: serializers must work on a fresh hydration too
    page.reload(wait_until="networkidle", timeout=90_000)
    page.wait_for_timeout(6000)
    pi2 = plot_info(page)
    r["plot_count_after_reload"] = len(pi2)
    r["scatter_id_after_reload"] = any(x["id"] == "scatter-chart" for x in pi2)
    r["grid_rows_after_reload"] = page.locator(".gridjs-tbody tr").count()
    page.screenshot(path=f"{SHOTS}/{LABEL}_05_reload.png", full_page=True)

    browser.close()

print(json.dumps({
    "label": LABEL, "results": r,
    "console_errors": [c for c in console if c["type"] == "error"],
    "console_warnings": [c for c in console if c["type"] == "warning"][:8],
    "page_errors": page_errors, "failed_requests": failed[:10],
    "bad_responses": sorted(set(bad))[:10],
}, indent=2, default=str))
