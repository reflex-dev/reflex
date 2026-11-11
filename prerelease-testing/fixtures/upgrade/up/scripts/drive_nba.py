"""Drive the reflex-examples `nba` app (pandas DataFrame -> rx.data_table/gridjs, plotly express figures
from computed vars, radix selects + range sliders). Server started with QA_NBA_EXTRAS=1 adds two plots
whose `layout` prop carries a plain-string title (literal / state-driven) -> the #7226 path.

Usage: drive_nba.py <url> <outdir> <tag>
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG = sys.argv[1:4]
run = Run(TAG, OUT)

PLOTS_JS = """() => [...document.querySelectorAll('.js-plotly-plot')].map(p => {
    const t = p.layout && p.layout.title;
    const g = p.querySelector('.gtitle');
    return {id: p.id || null, traces: (p.data || []).length,
            points: (p.calcdata || []).reduce((n, cd) => n + (cd ? cd.length : 0), 0),
            layout_title: t === undefined ? null : t,
            rendered_title: g ? g.textContent : null,
            names: (p.data || []).map(d => d.name || '').slice(0, 8)};
})"""


def plots(page):
    return page.evaluate(PLOTS_JS)


def pump(page, cond, timeout=15.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if cond():
                return True
        except Exception:  # noqa: BLE001
            pass
        page.wait_for_timeout(250)
    return bool(cond())


def badges(page):
    return page.evaluate("() => [...document.querySelectorAll('.rt-Badge')].map(b => b.innerText.trim())")


def click_track(page, idx, frac):
    """mouse-click a radix slider track at `frac` of its width (moves the nearest thumb, commits on pointerup)."""
    tr = page.locator(".rt-SliderRoot").nth(idx)
    box = tr.bounding_box()
    page.mouse.click(box["x"] + box["width"] * frac, box["y"] + box["height"] / 2)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context(viewport={"width": 1500, "height": 1100}, color_scheme="light")
    page = ctx.new_page()
    run.attach(page, "main")
    page.goto(URL, wait_until="load")
    page.locator(".gridjs-table").wait_for(timeout=90000)
    pump(page, lambda: len(plots(page)) >= 2 and all(x["points"] > 0 for x in plots(page)[:2]), 30)
    page.wait_for_timeout(1500)
    pl = plots(page)
    run.notes["plots_initial"] = pl
    hdr = [h.inner_text().strip() for h in page.locator(".gridjs-thead th").all()]
    summary = page.locator(".gridjs-summary").inner_text() if page.locator(".gridjs-summary").count() else None
    run.check("grid: gridjs table renders the DataFrame (9 columns, 10 rows, summary)", len(hdr) == 9 and page.locator(".gridjs-tbody tr").count() == 10 and summary and "of 320" in summary,
              f"headers={hdr} summary={summary}")
    n_plots = len(pl)
    run.check("plots: scatter + histogram render with data", n_plots >= 2 and pl[0]["points"] > 0 and pl[1]["points"] > 0, [(x["id"], x["traces"], x["points"]) for x in pl])
    run.check("titles: px figure titles render (scatter / histogram)", pl[0]["rendered_title"] == "NBA Age/Salary plot" and pl[1]["rendered_title"] == "Age/Salary Distribution",
              [(x["rendered_title"], x["layout_title"]) for x in pl[:2]])
    if n_plots >= 4:
        lit, st = pl[2], pl[3]
        run.notes["qa_titles_initial"] = {"literal": [lit["layout_title"], lit["rendered_title"]], "state": [st["layout_title"], st["rendered_title"]]}
        run.check("#7226: literal string layout title renders (QA plot)", "pass" if lit["rendered_title"] == "QA literal layout title" else "anomaly",
                  f"layout.title={lit['layout_title']!r} rendered={lit['rendered_title']!r}")
        run.check("#7226: state-driven string layout title renders (QA plot)", "pass" if st["rendered_title"] == "QA All players" else "anomaly",
                  f"layout.title={st['layout_title']!r} rendered={st['rendered_title']!r}")
    run.shot(page, "01_initial")
    # grid search + pagination
    page.locator(".gridjs-search-input").fill("Kentucky")
    ok = pump(page, lambda: "of 320" not in (page.locator(".gridjs-summary").inner_text() if page.locator(".gridjs-summary").count() else "of 320"), 8)
    s2 = page.locator(".gridjs-summary").inner_text() if page.locator(".gridjs-summary").count() else None
    run.check("grid: search filters rows", ok, s2)
    page.locator(".gridjs-search-input").fill("")
    pump(page, lambda: "of 320" in (page.locator(".gridjs-summary").inner_text() or ""), 8)
    first = page.locator(".gridjs-tbody tr td").first.inner_text()
    page.locator(".gridjs-pagination button", has_text="Next").first.click()
    ok = pump(page, lambda: page.locator(".gridjs-tbody tr td").first.inner_text() != first, 6)
    run.check("grid: pagination Next changes the page", ok, page.locator(".gridjs-summary").inner_text())
    # position select -> both figures recompute
    before = plots(page)
    page.get_by_role("combobox").nth(0).click()
    page.get_by_role("option", name="PG", exact=True).click()
    ok = pump(page, lambda: plots(page)[0]["points"] != before[0]["points"] and plots(page)[1]["points"] != before[1]["points"], 20)
    pg = plots(page)
    run.check("filter position=PG recomputes scatter + histogram (server-side computed vars)", ok and pg[0]["rendered_title"] == "NBA Age/Salary plot",
              f"points {[x['points'] for x in before[:2]]} -> {[x['points'] for x in pg[:2]]}, scatter traces {before[0]['traces']} -> {pg[0]['traces']} names={pg[0]['names']}")
    if len(pg) >= 4:
        run.notes["qa_titles_after_pg"] = [pg[3]["layout_title"], pg[3]["rendered_title"]]
        run.check("#7226: state-driven layout title follows the filter (QA plot)", "pass" if pg[3]["rendered_title"] == "QA PG players" else "anomaly",
                  f"layout.title={pg[3]['layout_title']!r} rendered={pg[3]['rendered_title']!r}")
    run.shot(page, "02_pg")
    # college select
    b2 = plots(page)
    page.get_by_role("combobox").nth(1).click()
    page.get_by_role("option", name="Kentucky", exact=True).click()
    ok = pump(page, lambda: plots(page)[0]["points"] != b2[0]["points"], 15)
    run.check("filter college=Kentucky narrows the figures", ok, f"{b2[0]['points']} -> {plots(page)[0]['points']}")
    # sliders: age min via track click, salary min via track click
    bd0 = badges(page)
    click_track(page, 0, 0.25)
    ok = pump(page, lambda: badges(page) != bd0, 8)
    bd1 = badges(page)
    click_track(page, 1, 0.3)
    ok2 = pump(page, lambda: badges(page) != bd1, 8)
    bd2 = badges(page)
    run.check("range sliders commit (on_value_commit) -> badges update", ok and ok2, f"{bd0} -> {bd1} -> {bd2}")
    page.wait_for_timeout(1500)
    run.notes["plots_after_filters"] = plots(page)
    run.shot(page, "03_filters")
    # back to All/All -> figures restored
    page.get_by_role("combobox").nth(0).click()
    page.get_by_role("option", name="All", exact=True).click()
    page.get_by_role("combobox").nth(1).click()
    page.get_by_role("option", name="All", exact=True).click()
    page.wait_for_timeout(2500)
    run.notes["plots_after_reset_selects"] = [(x["traces"], x["points"]) for x in plots(page)]
    # reload: computed figures re-hydrate (state kept per token: filters persist)
    page.reload(wait_until="load")
    page.locator(".gridjs-table").wait_for(timeout=60000)
    ok = pump(page, lambda: len(plots(page)) == n_plots and plots(page)[0]["points"] > 0, 30)
    page.wait_for_timeout(1000)
    pr = plots(page)
    run.check("reload: figures + titles re-render", ok and pr[0]["rendered_title"] == "NBA Age/Salary plot" and pr[1]["rendered_title"] == "Age/Salary Distribution",
              [(x["traces"], x["points"], x["rendered_title"]) for x in pr])
    run.notes["badges_after_reload"] = badges(page)
    run.shot(page, "04_reload")
    browser.close()
sys.exit(run.finish())
