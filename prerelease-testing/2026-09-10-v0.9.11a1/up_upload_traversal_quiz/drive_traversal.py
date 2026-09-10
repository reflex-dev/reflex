"""Playwright driver for the reflex-examples `traversal` app (rx.toast / sonner focus).

Usage:
    NO_PROXY=localhost,127.0.0.1 no_proxy=localhost,127.0.0.1 \
      $SB/envs/driver/bin/python drive_traversal.py <frontend_url> <artifacts_dir> <label>

Flows: initial 7x7 grid (1 red start, 1 green goal, 3 blue walls), radix slider via keyboard ->
"N walls" text + Generate Graph regenerates with N walls, radix select -> DFS -> Run -> the
self-chaining `run_dfs` event chain colors cells yellow and ends in an `rx.toast.success`
("Path found to [i,j]", top-center) or `rx.toast.error` ("No path found"); toast DOM attributes
(type / position), auto-dismiss, Clear resets, BFS run, stacking of two toasts, color-mode
toggle + toast in dark mode. Captures console / page errors / failed requests / screenshots.
"""

import re
import sys
import time

from drive_common import Run, wait_for

FRONTEND = sys.argv[1].rstrip("/")
ART = sys.argv[2]
LABEL = sys.argv[3]

CELL = ".rt-Grid > div"  # styles are emotion classes, not inline; cells are direct children of the radix Grid


def cell_colors(page):
    return page.evaluate(
        """(sel) => Array.from(document.querySelectorAll(sel)).map(e => getComputedStyle(e).backgroundColor)""",
        CELL,
    )


def color_counts(page):
    cols = cell_colors(page)
    named = {"rgb(255, 0, 0)": "red", "rgb(0, 128, 0)": "green", "rgb(0, 0, 255)": "blue",
             "rgb(255, 255, 0)": "yellow"}
    counts = {"red": 0, "green": 0, "blue": 0, "yellow": 0, "other": 0, "total": len(cols)}
    for c in cols:
        counts[named.get(c, "other")] += 1
    return counts


def toasts(page):
    return page.evaluate(
        """() => Array.from(document.querySelectorAll('[data-sonner-toast]')).map(t => ({
              text: t.innerText.trim(), type: t.getAttribute('data-type'),
              x: t.getAttribute('data-x-position'), y: t.getAttribute('data-y-position'),
              mounted: t.getAttribute('data-mounted'), visible: t.getAttribute('data-visible'),
              expanded: t.getAttribute('data-expanded'), styled: t.getAttribute('data-styled')}))"""
    )


def run_algorithm(run, page, algo, tag):
    # select algorithm via radix select
    page.get_by_role("combobox").click()
    page.get_by_role("option", name=algo).click()
    wait_for(lambda: page.get_by_role("combobox").inner_text().strip() == algo, 5)
    t0 = time.time()
    page.get_by_role("button", name="Run", exact=True).click()
    got = wait_for(lambda: len(toasts(page)) > 0, 40, 0.1)
    elapsed = time.time() - t0
    ts = toasts(page)
    counts = color_counts(page)
    page.wait_for_timeout(700)  # let the sonner slide-in animation settle before the screenshot
    run.shot(page, f"{tag}.png")
    text = ts[0]["text"] if ts else ""
    kind = "success" if text.startswith("Path found") else "error" if text.startswith("No path") else "?"
    run.record(
        f"{algo}_chain_ends_in_toast",
        "pass" if got and kind in ("success", "error") else "fail",
        f"toast after {elapsed:.1f}s: {ts[:1]} yellow_cells={counts['yellow']}",
    )
    if ts:
        t = ts[0]
        expect_type = "success" if kind == "success" else "error"
        attrs_ok = t["type"] == expect_type and t["y"] == "top" and t["x"] == "center"
        run.record(
            f"{algo}_toast_attributes",
            "pass" if attrs_ok else "fail",
            f"data-type={t['type']} (expect {expect_type}) position={t['y']}-{t['x']} (expect top-center) "
            f"styled={t['styled']} mounted={t['mounted']}",
        )
        if kind == "success":
            m = re.match(r"Path found to \[(\d+),(\d+)\]", text)
            run.record(f"{algo}_toast_text_format", "pass" if m else "fail", text)
    run.record(
        f"{algo}_yellow_progress_cells",
        "pass" if counts["yellow"] > 0 or kind == "error" else "anomaly",
        str(counts),
    )
    return ts, elapsed


with Run(ART, LABEL) as run:
    ctx, page = run.new_page()
    page.goto(FRONTEND, wait_until="networkidle")
    wait_for(lambda: page.locator(CELL).count() >= 49, 15)
    page.wait_for_timeout(800)
    run.shot(page, "01_initial.png")

    title_ok = page.title() == "Graph Traversal - Reflex"
    run.record("page_title", "pass" if title_ok else "fail", f"title={page.title()!r}")
    counts = color_counts(page)
    grid_ok = counts["total"] == 49 and counts["red"] == 1 and counts["green"] == 1 and counts["blue"] == 3
    run.record("initial_grid_7x7_1red_1green_3blue", "pass" if grid_ok else "fail", str(counts))
    run.record("walls_label", "pass" if page.get_by_text("3 walls").count() == 1 else "fail",
               "'3 walls' visible")
    run.record("select_placeholder", "pass" if page.get_by_text("Select an algorithm...").count() == 1 else "fail",
               "placeholder shown")

    # slider via keyboard: focus thumb, ArrowRight x2 -> 5 walls
    thumb = page.get_by_role("slider")
    thumb.focus()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    ok = wait_for(lambda: page.get_by_text("5 walls").count() == 1, 5)
    run.record("slider_keyboard_updates_walls", "pass" if ok else "fail",
               f"aria-valuenow={thumb.get_attribute('aria-valuenow')} label 5 walls={ok}")
    page.get_by_role("button", name="Generate Graph").click()
    ok = wait_for(lambda: color_counts(page)["blue"] == 5, 5)
    counts = color_counts(page)
    run.shot(page, "02_five_walls.png")
    run.record("generate_graph_uses_wall_count", "pass" if ok and counts["red"] == 1 and counts["green"] == 1 else "fail",
               str(counts))

    # Run without algorithm: no toast, no crash
    page.get_by_role("button", name="Run", exact=True).click()
    page.wait_for_timeout(800)
    run.record("run_without_algorithm_noop", "pass" if not toasts(page) else "anomaly",
               f"toasts={toasts(page)}")

    ts, _ = run_algorithm(run, page, "DFS", "03_dfs_toast")

    # auto-dismiss (sonner default 4s)
    gone = wait_for(lambda: len(toasts(page)) == 0, 12, 0.25)
    run.record("toast_auto_dismisses", "pass" if gone else "fail", f"toasts remaining={toasts(page)}")

    page.get_by_role("button", name="Clear", exact=True).click()
    ok = wait_for(lambda: color_counts(page)["yellow"] == 0, 5)
    run.record("clear_resets_grid", "pass" if ok else "fail", str(color_counts(page)))

    # BFS on a fresh 0-wall graph -> guaranteed path
    thumb.focus()
    for _ in range(5):
        page.keyboard.press("ArrowLeft")
    wait_for(lambda: page.get_by_text("0 walls").count() == 1, 5)
    page.get_by_role("button", name="Generate Graph").click()
    wait_for(lambda: color_counts(page)["blue"] == 0, 5)
    ts, elapsed = run_algorithm(run, page, "BFS", "04_bfs_toast")
    run.record("bfs_zero_walls_finds_path", "pass" if ts and ts[0]["text"].startswith("Path found") else "fail",
               f"{ts[:1]} elapsed={elapsed:.1f}s")

    # stacking: immediately run DFS again while BFS toast still visible
    page.get_by_role("combobox").click()
    page.get_by_role("option", name="DFS").click()
    page.get_by_role("button", name="Run", exact=True).click()
    ok = wait_for(lambda: len(toasts(page)) >= 2, 40, 0.1)
    run.shot(page, "05_two_toasts.png")
    run.record("two_toasts_stack", "pass" if ok else "anomaly", f"toasts={toasts(page)}")

    # hover expands the stack (sonner behaviour)
    if ok:
        try:
            page.locator("[data-sonner-toast]").first.hover(timeout=3000)
            page.wait_for_timeout(400)
            exp = [t["expanded"] for t in toasts(page)]
            run.record("toaster_hover_expands", "pass" if "true" in exp else "anomaly", f"data-expanded={exp}")
            run.shot(page, "06_toasts_hover.png")
            page.mouse.move(5, 5)
        except Exception as e:  # noqa: BLE001
            run.record("toaster_hover_expands", "skipped", f"hover failed (toast gone?): {str(e)[:120]}")

    wait_for(lambda: len(toasts(page)) == 0, 15, 0.25)

    # color mode toggle -> dark; toast in dark mode
    html_class_before = page.evaluate("document.documentElement.className")
    page.locator("button:has(.lucide-sun), button:has(.lucide-moon)").first.click()  # rx.color_mode.button
    ok = wait_for(lambda: page.evaluate("document.documentElement.className") != html_class_before, 5)
    html_class_after = page.evaluate("document.documentElement.className")
    run.record("color_mode_toggle", "pass" if ok else "fail",
               f"html.class {html_class_before!r} -> {html_class_after!r}")
    page.get_by_role("button", name="Run", exact=True).click()
    got = wait_for(lambda: len(toasts(page)) > 0, 40, 0.1)
    run.shot(page, "07_dark_toast.png")
    tt = toasts(page)
    theme = page.evaluate("Array.from(document.querySelectorAll('[data-sonner-toaster]')).map(t => t.getAttribute('data-sonner-theme'))")
    run.record("toast_in_dark_mode", "pass" if got else "fail", f"toast={tt[:1]} toaster data-sonner-theme={theme}")
    run.record("toaster_theme_follows_dark_mode", "pass" if theme and all(t == "dark" for t in theme) else "anomaly",
               f"data-sonner-theme per <ol>={theme}")
    run.record("sonner_one_ol_per_position", "pass" if len(theme) == 2 else "anomaly",
               f"{len(theme)} toaster <ol> elements (default bottom-right + top-center in use)")

    # dark mode persists across reload (local storage) and grid still renders
    page.reload(wait_until="networkidle")
    wait_for(lambda: page.locator(CELL).count() >= 49, 15)
    cls = page.evaluate("document.documentElement.className")
    run.record("dark_mode_persists_reload", "pass" if "dark" in cls else "anomaly", f"html.class={cls!r}")
    run.shot(page, "08_dark_reload.png")

    # sonner package version actually served by vite (dev server module URL)
    ver = page.evaluate(
        """() => { const s = performance.getEntriesByType('resource').map(e => e.name).filter(n => /sonner/.test(n)); return s.slice(0, 3); }"""
    )
    run.record("sonner_module_urls", "pass", f"{ver}")
    ctx.close()
