"""Driver for the reflex-examples `github-stats` app (data source stubbed offline).

usage: drive_github.py <frontend_url> <artifacts_dir> <label> [<app_dir>]

Exercises rx.recharts.bar_chart with four rx.recharts.bar series over a state-driven `data=` list,
x_axis/y_axis/legend/graphing_tooltip, rx.foreach chips with an event-arg handler
(State.remove_user(user)), two `@rx.event(background=True)` fetchers, rx.LocalStorage vars
restored on reload, and the dynamic route /widget/[selected_user_param] with a query param.
"""

import json
import sys

from drive_common import Run, wait_for

URL, ART, LABEL = sys.argv[1], sys.argv[2], sys.argv[3]
APP_DIR = sys.argv[4] if len(sys.argv) > 4 else None

BARS = ".recharts-bar-rectangle"


def n_bars(page):
    return page.locator(BARS).count()


def x_ticks(page):
    # SVG <text>: inner_text() is always "" in Chromium, must use text_content()
    # recharts 3.x puts tick labels in .recharts-<axis>-tick-labels, NOT inside .recharts-xAxis
    return [
        (t.text_content() or "").strip()
        for t in page.locator(".recharts-xAxis-tick-labels .recharts-cartesian-axis-tick-value").all()
    ]


def bar_sizes(page):
    """Rendered size of each bar path, so 'the SVG element exists' != 'the bar is drawn'."""
    return page.evaluate(
        "() => Array.from(document.querySelectorAll('.recharts-bar-rectangle')).map(g => {"
        " const p = g.querySelector('path'); if (!p) return null; const bb = p.getBBox();"
        " return {w: Math.round(bb.width), h: Math.round(bb.height)}; })"
    )


def add_user(page, name):
    page.fill("#username", name)
    page.get_by_role("button", name="Get Stats").click()


with Run(ART, LABEL) as run:
    ctx, page = run.new_page(LABEL)
    page.set_default_timeout(25000)

    page.goto(URL, wait_until="load")
    ok = wait_for(lambda: "Github Stats" in page.inner_text("body"), 60)
    run.record("load_index", "pass" if ok else "fail", f"heading present={ok}")
    page.wait_for_timeout(1500)
    run.shot(page, "01_index.png", full_page=True)
    run.record(
        "empty_chart_renders",
        "pass" if page.locator(".recharts-wrapper").count() >= 1 else "fail",
        f"recharts wrappers={page.locator('.recharts-wrapper').count()}, bars={n_bars(page)}",
    )

    # --- add one user: background fetch + chart ---------------------------------------
    add_user(page, "masenf")
    saw_fetching = wait_for(lambda: "Fetching Data..." in page.inner_text("body"), 5)
    got = wait_for(lambda: n_bars(page) == 4, 30)
    run.record(
        "add_user_one",
        "pass" if got else "fail",
        f"bars={n_bars(page)} (expect 4 series x 1 category), saw 'Fetching Data...'={saw_fetching}",
    )
    run.record(
        "background_event_spinner",
        "pass" if saw_fetching else "anomaly",
        "the @rx.event(background=True) fetch window was visible in the DOM",
    )
    run.record("x_axis_tick", "pass" if x_ticks(page) == ["masenf"] else "fail", f"ticks={x_ticks(page)}")
    # poll: the <g class="recharts-bar-rectangle"> groups appear a beat before their <path>,
    # so measuring the bbox the instant the group count hits 4 races the paint
    wait_for(lambda: all(s and s["h"] > 0 and s["w"] > 0 for s in bar_sizes(page)) and len(bar_sizes(page)) == 4, 15)
    sizes = bar_sizes(page)
    drawn = [s for s in sizes if s and s["h"] > 0 and s["w"] > 0]
    run.record(
        "index_bars_drawn",
        "pass" if len(drawn) == 4 else "anomaly",
        f"{len(drawn)}/{len(sizes)} bar paths have a non-zero bbox; sizes={sizes} "
        "(index chart is rx.box(width='100%', height='15em'))",
    )
    ta = page.locator("textarea").first.input_value()
    has_login = '"login": "masenf"' in ta
    run.record(
        "cached_var_textarea",
        "pass" if has_login else "fail",
        f"data_pretty len={len(ta)} has_login={has_login}",
    )
    run.record(
        "chip_rendered",
        "pass" if "masenf" in page.inner_text("body") else "fail",
        "rx.foreach chip for masenf",
    )
    run.shot(page, "02_one_user.png", full_page=True)

    # --- tooltip (rx.recharts.graphing_tooltip(cursor=False)) -------------------------
    bar = page.locator(BARS).first
    bar.hover()
    page.wait_for_timeout(800)
    tip = page.locator(".recharts-tooltip-wrapper")
    tip_text = tip.first.inner_text() if tip.count() else ""
    run.record(
        "tooltip_on_hover",
        "pass" if tip.count() and tip_text.strip() else "anomaly",
        f"wrappers={tip.count()} text={tip_text[:80]!r}",
    )
    cursor = page.locator(".recharts-rectangle.recharts-tooltip-cursor").count()
    run.record("tooltip_cursor_false", "pass" if cursor == 0 else "anomaly", f"tooltip-cursor elements={cursor}")
    run.shot(page, "03_tooltip.png")

    # --- second user ------------------------------------------------------------------
    add_user(page, "picklelo")
    got2 = wait_for(lambda: n_bars(page) == 8, 30)
    run.record("add_user_two", "pass" if got2 else "fail", f"bars={n_bars(page)} ticks={x_ticks(page)}")
    run.shot(page, "04_two_users.png", full_page=True)

    # --- unknown user: the fetcher returns None ---------------------------------------
    errs_before = len(run.page_errors)
    add_user(page, "nosuchuser")
    page.wait_for_timeout(4000)
    settled = wait_for(lambda: "Fetching Data..." not in page.inner_text("body"), 20)
    run.record(
        "unknown_user_no_crash",
        "pass" if n_bars(page) == 8 and settled and len(run.page_errors) == errs_before else "fail",
        f"bars={n_bars(page)} spinner_gone={settled} new_page_errors={len(run.page_errors) - errs_before}",
    )
    run.shot(page, "05_unknown_user.png", full_page=True)

    # --- remove chips (event handler taking the foreach item) -------------------------
    xs = page.get_by_role("button", name="X")
    run.record("remove_buttons", "pass" if xs.count() == 3 else "fail", f"X buttons={xs.count()}")
    xs.last.click()  # nosuchuser
    page.wait_for_timeout(1500)
    xs.last.click()  # picklelo
    back_to_4 = wait_for(lambda: n_bars(page) == 4, 25)
    run.record(
        "remove_user",
        "pass" if back_to_4 and x_ticks(page) == ["masenf"] else "fail",
        f"bars={n_bars(page)} ticks={x_ticks(page)}",
    )
    run.shot(page, "06_after_remove.png", full_page=True)

    # --- LocalStorage keys + reload restore ------------------------------------------
    ls = page.evaluate("() => Object.fromEntries(Object.entries(localStorage).map(([k,v]) => [k, v.length]))")
    (run.art / "localstorage.json").write_text(json.dumps(ls, indent=2, sort_keys=True))
    run.record(
        "localstorage_keys",
        "pass" if any("user_stats_json" in k for k in ls) else "fail",
        f"keys={sorted(ls)}",
    )
    page.reload(wait_until="load")
    restored = wait_for(lambda: n_bars(page) == 4, 40)
    run.record(
        "localstorage_restores_after_reload",
        "pass" if restored and x_ticks(page) == ["masenf"] else "fail",
        f"bars={n_bars(page)} ticks={x_ticks(page)}",
    )
    run.shot(page, "07_after_reload.png", full_page=True)

    # --- color mode -------------------------------------------------------------------
    try:
        page.locator("button.rt-IconButton").first.click()
        page.wait_for_timeout(1200)
        cls = page.evaluate("() => document.querySelector('.radix-themes')?.className || document.documentElement.className")
        run.record("color_mode_toggle", "pass" if "dark" in (cls or "") else "anomaly", f"class={cls!r}")
        run.shot(page, "08_dark.png", full_page=True)
        page.locator("button.rt-IconButton").first.click()
        page.wait_for_timeout(800)
    except Exception as e:  # noqa: BLE001
        run.record("color_mode_toggle", "fail", str(e)[:200])

    # --- dynamic route /widget/[selected_user_param] ----------------------------------
    page.goto(URL.rstrip("/") + "/widget/masenf", wait_until="load")
    ok = wait_for(lambda: "Github Stats for masenf" in page.inner_text("body"), 40)
    wbars = wait_for(lambda: n_bars(page) == 4, 40)
    run.record(
        "widget_dynamic_route",
        "pass" if ok and wbars else "fail",
        f"heading_ok={ok} bars={n_bars(page)} ticks={x_ticks(page)}",
    )
    wsizes = bar_sizes(page)
    wdrawn = [s for s in wsizes if s and s["h"] > 0 and s["w"] > 0]
    run.record(
        "widget_bars_drawn",
        "pass" if len(wdrawn) == 4 else "anomaly",
        f"{len(wdrawn)}/{len(wsizes)} bar paths drawn; sizes={wsizes} (widget chart is 100vw x 85vh)",
    )
    legend = page.locator(".recharts-legend-wrapper .recharts-legend-item").count()
    run.record("widget_legend", "pass" if legend == 4 else "fail", f"legend items={legend}")
    run.shot(page, "09_widget.png", full_page=True)

    page.goto(URL.rstrip("/") + "/widget/masenf?appearance=dark", wait_until="load")
    ok = wait_for(lambda: "Github Stats for masenf" in page.inner_text("body"), 40)
    wait_for(lambda: n_bars(page) == 4, 40)
    dark = page.evaluate(
        "() => Array.from(document.querySelectorAll('.radix-themes')).map(e => e.className).join('|')"
    )
    run.record(
        "widget_appearance_param",
        "pass" if "dark" in dark else "anomaly",
        f"radix-themes classes={dark!r} -- rx.theme(appearance=...) is stripped by "
        "Theme._render().remove_props('appearance'), so ?appearance=dark has no effect "
        "(see probes/theme_appearance_probe.py; identical on 0.9.10.post2)",
    )

    # --- classify the console noise explicitly so it is comparable across versions ----
    chart_size = [m for m in run.console if "of chart should be greater than 0" in m["text"]]
    run.record(
        "console_recharts_chart_size_warning",
        "anomaly" if chart_size else "pass",
        f"{len(chart_size)} recharts 'width(-1) and height(-1)' warnings",
    )
    readonly = [m for m in run.console if "without an `onChange` handler" in m["text"]]
    run.record(
        "console_readonly_textarea_error",
        "anomaly" if readonly else "pass",
        f"{len(readonly)} React read-only-field errors (app passes rx.text_area(value=...) with no on_change)",
    )
    other = [
        m
        for m in run.unexpected_console()
        if "of chart should be greater than 0" not in m["text"]
        and "without an `onChange` handler" not in m["text"]
    ]
    run.record(
        "console_other",
        "pass" if not other else "anomaly",
        f"{len(other)} other console errors/warnings: {[m['text'][:90] for m in other]}",
    )
    run.shot(page, "10_widget_dark.png", full_page=True)

    if APP_DIR:
        vers = {}
        from pathlib import Path

        for name in ("recharts", "react", "react-dom", "react-router", "vite"):
            pj = Path(APP_DIR) / ".web" / "node_modules" / name / "package.json"
            if pj.exists():
                vers[name] = json.loads(pj.read_text()).get("version")
        (run.art / "npm_versions.json").write_text(json.dumps(vers, indent=2, sort_keys=True))
        run.record("recharts_version", "pass" if vers.get("recharts") else "fail", json.dumps(vers))

    ctx.close()
