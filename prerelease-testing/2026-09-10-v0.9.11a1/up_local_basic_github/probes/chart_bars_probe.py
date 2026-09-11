"""Quantify the github-stats index-chart 'bars exist but are never painted' glitch.

usage: chart_bars_probe.py <frontend_url> <out.json> <iterations>

Per iteration, in a FRESH browser context (empty localStorage):
  A) add a user on `/` and poll for up to 20 s for each of the 4 `.recharts-bar-rectangle`
     groups to contain a <path> with a non-zero bbox
  B) reload the page (data now in rx.LocalStorage, so it is present at mount) and poll again
  C) resize the viewport and poll again
Also records the recharts chart-size console warnings seen per iteration.
"""

import json
import sys
import time

from playwright.sync_api import sync_playwright

URL, OUT, N = sys.argv[1], sys.argv[2], int(sys.argv[3])

BBOX = (
    "() => Array.from(document.querySelectorAll('.recharts-bar-rectangle')).map(g => {"
    " const p = g.querySelector('path'); if (!p) return null; const b = p.getBBox();"
    " return {w: Math.round(b.width), h: Math.round(b.height)}; })"
)


def poll_drawn(page, timeout=20.0):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        last = page.evaluate(BBOX)
        drawn = [s for s in last if s and s["w"] > 0 and s["h"] > 0]
        if len(drawn) == 4:
            return round(time.time() - t0, 2), last
        time.sleep(0.25)
    return None, last


results = []
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for i in range(N):
        warns = []
        ctx = b.new_context(viewport={"width": 1280, "height": 720})
        page = ctx.new_page()
        page.on(
            "console",
            lambda m: warns.append(m.text[:60]) if "of chart should be greater than 0" in m.text else None,
        )
        page.goto(URL, wait_until="load")
        page.wait_for_timeout(2500)
        page.fill("#username", "masenf")
        page.get_by_role("button", name="Get Stats").click()
        page.wait_for_function(
            "() => document.querySelectorAll('.recharts-bar-rectangle').length === 4", timeout=30000
        )
        t_fresh, bb_fresh = poll_drawn(page)

        page.reload(wait_until="load")
        page.wait_for_function(
            "() => document.querySelectorAll('.recharts-bar-rectangle').length === 4", timeout=30000
        )
        t_reload, bb_reload = poll_drawn(page)

        page.set_viewport_size({"width": 1100, "height": 800})
        t_resize, bb_resize = poll_drawn(page, timeout=8.0)

        results.append(
            {
                "iteration": i,
                "fresh_add_user": {"drawn_after_s": t_fresh, "bbox": bb_fresh},
                "after_reload": {"drawn_after_s": t_reload, "bbox": bb_reload},
                "after_resize": {"drawn_after_s": t_resize, "bbox": bb_resize},
                "chart_size_warnings": len(warns),
            }
        )
        print(
            f"iter {i}: fresh={t_fresh} reload={t_reload} resize={t_resize} warns={len(warns)}",
            flush=True,
        )
        ctx.close()
    b.close()

summary = {
    "fresh_drawn": sum(1 for r in results if r["fresh_add_user"]["drawn_after_s"] is not None),
    "reload_drawn": sum(1 for r in results if r["after_reload"]["drawn_after_s"] is not None),
    "resize_drawn": sum(1 for r in results if r["after_resize"]["drawn_after_s"] is not None),
    "n": len(results),
    "total_chart_size_warnings": sum(r["chart_size_warnings"] for r in results),
}
print("SUMMARY:", json.dumps(summary))
with open(OUT, "w") as f:
    json.dump({"summary": summary, "results": results}, f, indent=2)
