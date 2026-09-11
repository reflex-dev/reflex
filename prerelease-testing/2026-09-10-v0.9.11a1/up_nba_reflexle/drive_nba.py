"""Drive the reflex-examples `nba` app end to end in Chromium.

usage: drive_nba.py <frontend_url> <artifacts_dir> <label> [<app_dir>]

Exercises: rx.data_table (gridjs) search/sort/pagination, the two rx.plotly figures
(px.scatter with a lowess trendline via statsmodels + px.histogram) recomputed from pandas
through cached @rx.var, the position/college rx.select filters, the two range rx.slider
filters (on_value_commit), the empty-dataframe -> bare go.Figure() path, color mode, and a
viewport resize against use_resize_handler=True.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drive_common import Run, wait_for  # noqa: E402

URL, ART, LABEL = sys.argv[1], sys.argv[2], sys.argv[3]
APP_DIR = sys.argv[4] if len(sys.argv) > 4 else None

PLOT_FP_JS = """
() => {
  const plots = [...document.querySelectorAll('.js-plotly-plot')];
  return plots.map(p => {
    const svg = p.querySelector('svg.main-svg');
    return {
      traces: p.querySelectorAll('g.trace').length,
      points: p.querySelectorAll('g.trace .point, g.trace path.point').length,
      titles: [...p.querySelectorAll('.gtitle')].map(t => t.textContent),
      legend: [...p.querySelectorAll('.legend .legendtext')].map(t => t.textContent),
      xticks: [...p.querySelectorAll('.xtick text')].map(t => t.textContent).join(','),
      yticks: [...p.querySelectorAll('.ytick text')].map(t => t.textContent).join(','),
      width: p.getBoundingClientRect().width,
      svglen: svg ? svg.innerHTML.length : 0,
    };
  });
}
"""


def plot_fp(page):
    return page.evaluate(PLOT_FP_JS)


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:12]


def table_rows(page):
    return page.evaluate(
        "() => [...document.querySelectorAll('table tbody tr')].map(r => r.innerText.replace(/\\s+/g,' ').trim())"
    )


def pick_select(page, run, name, trigger_index, option_text):
    """Open the Nth radix select trigger and click the option with that text."""
    triggers = page.locator("button[role='combobox'], [role='combobox']")
    triggers.nth(trigger_index).click()
    page.wait_for_timeout(400)
    opt = page.locator("[role='option']").filter(has_text=re.compile(rf"^{re.escape(option_text)}$"))
    if opt.count() == 0:
        opt = page.get_by_role("option", name=option_text, exact=True)
    opt.first.click()
    page.wait_for_timeout(1500)


def nudge_slider(page, run, thumb_index, presses, key="ArrowRight"):
    """Keyboard-nudge a radix slider thumb (fine for the 18..50 age range)."""
    thumbs = page.locator("[role='slider']")
    n = thumbs.count()
    thumbs.nth(thumb_index).click()
    for _ in range(presses):
        page.keyboard.press(key)
        page.wait_for_timeout(60)
    # on_value_commit fires on keyup/pointerup; blur to be safe
    page.keyboard.press("Tab")
    page.wait_for_timeout(1500)
    return n


def drag_slider(page, thumb_index, fraction):
    """Mouse-drag a radix slider thumb to `fraction` of its own track width.

    Needed for the salary slider: its range is 0..25_000_000 with step 1, so a keyboard
    ArrowRight moves one dollar and the M-rounded badge never changes.
    """
    thumbs = page.locator("[role='slider']")
    thumb = thumbs.nth(thumb_index)
    tb = thumb.bounding_box()
    track = thumb.evaluate_handle("t => t.closest('.rt-SliderRoot') || t.parentElement")
    trb = track.as_element().bounding_box()
    page.mouse.move(tb["x"] + tb["width"] / 2, tb["y"] + tb["height"] / 2)
    page.mouse.down()
    page.mouse.move(trb["x"] + trb["width"] * fraction, tb["y"] + tb["height"] / 2, steps=12)
    page.mouse.up()
    page.wait_for_timeout(1800)
    return page.evaluate(
        "() => [...document.querySelectorAll('[role=slider]')].map(s=>s.getAttribute('aria-valuenow'))"
    )


with Run(ART, LABEL) as run:
    ctx, page = run.new_page("nba")
    page.set_viewport_size({"width": 1500, "height": 1000})
    page.goto(URL, wait_until="load", timeout=90_000)
    page.wait_for_timeout(3000)

    # 1. page loads, navbar
    ok = wait_for(lambda: page.locator("text=NBA Data").count() > 0, 30)
    run.record("nba_page_loads", "pass" if ok else "fail", f"title={page.title()!r} navbar_found={ok}")
    run.shot(page, "01_index.png", full_page=True)

    # 2. data_table renders with the vendored 457-row dataset
    ok = wait_for(lambda: len(table_rows(page)) > 0, 40)
    rows = table_rows(page)
    has_bradley = any("Avery Bradley" in r for r in rows)
    run.record(
        "data_table_renders",
        "pass" if ok and has_bradley else "fail",
        f"visible_rows={len(rows)} first={rows[0] if rows else None!r} avery_bradley={has_bradley}",
    )

    # 3. search
    search = page.locator("input[placeholder*='Type a keyword'], .gridjs-search-input, input[type='search']")
    if search.count() == 0:
        search = page.locator("input").first
    search.first.fill("Curry")
    page.wait_for_timeout(1500)
    frows = table_rows(page)
    run.record(
        "data_table_search",
        "pass" if frows and all("Curry" in r for r in frows) else "fail",
        f"rows_after_search={len(frows)} rows={frows[:3]}",
    )
    run.shot(page, "02_table_search.png")
    search.first.fill("")
    page.wait_for_timeout(1200)

    # 4. sort by clicking the first sortable header
    before = table_rows(page)[:3]
    th = page.locator("th").first
    th.click()
    page.wait_for_timeout(1200)
    after = table_rows(page)[:3]
    run.record(
        "data_table_sort",
        "pass" if before and after and before != after else "fail",
        f"before={before[:1]} after={after[:1]}",
    )

    # 5. pagination
    nxt = page.locator("button:has-text('Next'), .gridjs-pagination button").last
    pg_before = table_rows(page)[:2]
    try:
        nxt.click()
        page.wait_for_timeout(1200)
        pg_after = table_rows(page)[:2]
        run.record(
            "data_table_pagination",
            "pass" if pg_before != pg_after else "fail",
            f"page1={pg_before[:1]} page2={pg_after[:1]}",
        )
    except Exception as e:  # noqa: BLE001
        run.record("data_table_pagination", "fail", f"exception: {e}")

    # 6/7/8. the two plotly figures
    ok = wait_for(lambda: len(plot_fp(page)) == 2 and plot_fp(page)[0]["traces"] > 0, 40)
    fps = plot_fp(page)
    run.record(
        "plotly_two_figures_render",
        "pass" if len(fps) == 2 else "fail",
        f"plot_count={len(fps)} fingerprints={json.dumps(fps)}",
    )
    titles = [t for fp in fps for t in fp["titles"]]
    run.record(
        "plotly_titles",
        "pass" if any("NBA Age/Salary plot" in t for t in titles) and any("Age/Salary Distribution" in t for t in titles) else "fail",
        f"titles={titles}",
    )
    # the lowess trendline (statsmodels) adds an extra trace beyond the 5 position groups
    run.record(
        "plotly_scatter_trendline_traces",
        "pass" if fps and fps[0]["traces"] >= 6 else "fail",
        f"scatter traces={fps[0]['traces'] if fps else None} legend={fps[0]['legend'] if fps else None} "
        "(5 position symbols + overall lowess trendline expected)",
    )
    run.shot(page, "03_plots_default.png", full_page=True)
    base_fp = digest(fps)

    # 9. position select -> figure recompute
    try:
        pick_select(page, run, "position", 0, "PG")
        fps_pg = plot_fp(page)
        run.record(
            "select_position_filters_plots",
            "pass" if digest(fps_pg) != base_fp and fps_pg[0]["traces"] > 0 else "fail",
            f"traces {fps[0]['traces']}->{fps_pg[0]['traces']} legend={fps_pg[0]['legend']} fp {base_fp}->{digest(fps_pg)}",
        )
        run.shot(page, "04_position_PG.png", full_page=True)
    except Exception as e:  # noqa: BLE001
        run.record("select_position_filters_plots", "fail", f"exception: {e}")

    # 10. college select -> figure recompute
    try:
        pick_select(page, run, "college", 1, "Kentucky")
        fps_ky = plot_fp(page)
        run.record(
            "select_college_filters_plots",
            "pass" if fps_ky and digest(fps_ky) != digest(fps_pg) else "fail",
            f"traces={fps_ky[0]['traces']} points={fps_ky[0]['points']} fp={digest(fps_ky)}",
        )
        run.shot(page, "05_college_kentucky.png", full_page=True)
    except Exception as e:  # noqa: BLE001
        run.record("select_college_filters_plots", "fail", f"exception: {e}")

    # reset college back to All so later checks have data
    try:
        pick_select(page, run, "college_reset", 1, "All")
        pick_select(page, run, "position_reset", 0, "All")
    except Exception as e:  # noqa: BLE001
        run.record("select_reset_to_all", "anomaly", f"could not reset selects: {e}")

    # 11. age slider on_value_commit -> badge text
    badges_before = page.evaluate(
        "() => [...document.querySelectorAll('span,div')].map(e=>e.textContent).filter(t=>t&&t.startsWith('Min Age:')||t&&t.startsWith('Max Age:')).slice(0,2)"
    )
    n_thumbs = nudge_slider(page, run, 0, 5)
    badges_after = page.evaluate(
        "() => [...document.querySelectorAll('span,div')].map(e=>e.textContent).filter(t=>t&&t.startsWith('Min Age:')||t&&t.startsWith('Max Age:')).slice(0,2)"
    )
    run.record(
        "slider_age_commit",
        "pass" if badges_before != badges_after else "fail",
        f"thumbs_on_page={n_thumbs} badges {badges_before} -> {badges_after}",
    )

    # 12. salary slider
    sal_before = page.evaluate(
        "() => [...document.querySelectorAll('span,div')].map(e=>e.textContent).filter(t=>t&&t.startsWith('Min Sal:')||t&&t.startsWith('Max Sal:')).slice(0,2)"
    )
    aria = drag_slider(page, 2, 0.40)
    sal_after = page.evaluate(
        "() => [...document.querySelectorAll('span,div')].map(e=>e.textContent).filter(t=>t&&t.startsWith('Min Sal:')||t&&t.startsWith('Max Sal:')).slice(0,2)"
    )
    fps_after_sliders = plot_fp(page)
    run.record(
        "slider_salary_commit",
        "pass" if sal_before != sal_after else "fail",
        f"badges {sal_before} -> {sal_after}; aria-valuenow={aria}; "
        f"plot traces={fps_after_sliders[0]['traces'] if fps_after_sliders else None}",
    )
    run.shot(page, "06_after_sliders.png", full_page=True)

    # 13. filter down to an empty dataframe -> bare go.Figure()
    try:
        pick_select(page, run, "position_empty", 0, "C")
        pick_select(page, run, "college_empty", 1, "Louisiana Tech")
        page.wait_for_timeout(1500)
        fps_empty = plot_fp(page)
        empty_ok = fps_empty and all(fp["traces"] == 0 for fp in fps_empty)
        run.record(
            "empty_dataframe_bare_figure",
            "pass" if empty_ok else "anomaly",
            f"fingerprints={json.dumps(fps_empty)} (expect traces=0 on both, no crash)",
        )
        run.shot(page, "07_empty_filters.png", full_page=True)
        pick_select(page, run, "college_restore", 1, "All")
        pick_select(page, run, "position_restore", 0, "All")
        page.wait_for_timeout(1500)
        fps_restore = plot_fp(page)
        run.record(
            "recover_from_empty_dataframe",
            "pass" if fps_restore and fps_restore[0]["traces"] > 0 else "fail",
            f"traces after restore={fps_restore[0]['traces'] if fps_restore else None}",
        )
    except Exception as e:  # noqa: BLE001
        run.record("empty_dataframe_bare_figure", "fail", f"exception: {e}")

    # 14. color mode (navbar rx.color_mode.button() is the only rt-IconButton on the page)
    before_cls = page.evaluate("() => document.documentElement.className")
    page.locator("button.rt-IconButton").first.click()
    page.wait_for_timeout(1500)
    after_cls = page.evaluate("() => document.documentElement.className")
    plot_bg = page.evaluate(
        "() => { const p=document.querySelector('.js-plotly-plot .bg'); return p? p.getAttribute('style') : null }"
    )
    run.record(
        "color_mode_toggle",
        "pass" if before_cls != after_cls else "fail",
        f"documentElement.class {before_cls!r} -> {after_cls!r}; plot .bg style={plot_bg!r} "
        "(plotly figures are built with the default template, so they stay light - app behaviour)",
    )
    run.shot(page, "08_after_color_mode_click.png", full_page=True)

    # 15. resize handler
    w_before = [fp["width"] for fp in plot_fp(page)]
    page.set_viewport_size({"width": 800, "height": 900})
    page.wait_for_timeout(2500)
    w_after = [fp["width"] for fp in plot_fp(page)]
    run.record(
        "plotly_use_resize_handler",
        "pass" if w_before and w_after and w_before[0] != w_after[0] else "anomaly",
        f"plot widths {w_before} -> {w_after} after viewport 1500->800",
    )
    run.shot(page, "09_narrow_viewport.png", full_page=True)
    page.set_viewport_size({"width": 1500, "height": 1000})
    page.wait_for_timeout(1500)

    # 16. hard reload keeps working (hydrate path)
    page.reload(wait_until="load")
    page.wait_for_timeout(4000)
    fps_reload = plot_fp(page)
    rows_reload = table_rows(page)
    run.record(
        "reload_rehydrates",
        "pass" if fps_reload and fps_reload[0]["traces"] > 0 and rows_reload else "fail",
        f"traces={fps_reload[0]['traces'] if fps_reload else None} rows={len(rows_reload)}",
    )
    run.shot(page, "10_after_reload.png", full_page=True)

    # 17. record the installed frontend package versions
    if APP_DIR:
        pkg = Path(APP_DIR) / ".web" / "package.json"
        if pkg.exists():
            data = json.loads(pkg.read_text())
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            interesting = {k: v for k, v in deps.items() if any(s in k for s in ("plotly", "react", "vite", "gridjs", "grid.js", "radix", "sonner", "router"))}
            (Path(ART) / "npm_versions.json").write_text(json.dumps(deps, indent=2, sort_keys=True))
            run.record("npm_versions_recorded", "pass", json.dumps(interesting, sort_keys=True))

    unexpected = run.unexpected_console()
    run.record(
        "browser_console_clean",
        "pass" if not unexpected else "anomaly",
        f"{len(unexpected)} unexpected console error/warning(s): {json.dumps(unexpected[:8], ensure_ascii=False)}",
    )
    run.record(
        "no_bad_http_responses",
        "pass" if not run.bad else "anomaly",
        f"{len(run.bad)} failed/4xx-5xx: {json.dumps(run.bad[:8])}",
    )
    run.record(
        "no_page_errors",
        "pass" if not run.page_errors else "fail",
        f"{len(run.page_errors)}: {json.dumps(run.page_errors[:5])}",
    )
    ctx.close()
