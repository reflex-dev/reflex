"""Drive the enterprise highcharts demo (+ /qa State-driven charts added by this cluster).

Usage: drive_highcharts.py <base_url> <out_dir> <expected_venv> <label>
"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from qa_common import Session, assert_driver_and_server  # noqa: E402

base, out, venv, label = sys.argv[1:5]
info = assert_driver_and_server(venv)


def scenario(s, name, fn, *a):
    try:
        fn(*a)
    except Exception:
        s.check(f"{name}: scenario completed", False, traceback.format_exc()[-700:])


def main_page(s, p):
    p.goto(base + "/", wait_until="networkidle")
    p.wait_for_selector(".highcharts-root")
    p.wait_for_timeout(1500)
    s.check("index: 2 charts render (composed + options)", p.locator(".highcharts-root").count() == 2, p.locator(".highcharts-root").count())
    c0 = p.locator(".highcharts-container").nth(0)
    c1 = p.locator(".highcharts-container").nth(1)
    PT = ".highcharts-point[class*='highcharts-color-']"  # excludes the hover state-marker graphic
    counts = [c0.locator(f".highcharts-series-0 {PT}").count(), c0.locator(f".highcharts-series-1 {PT}").count(), c1.locator(PT).count()]
    s.check("composed: 6 columns + 6 line markers; options chart: pie 3 slices", counts == [6, 6, 3], counts)
    pt = c0.locator(f".highcharts-series-1 {PT}").nth(2)
    bb = pt.bounding_box()
    for dx in (0, 2, -2):  # several pointer moves so the Highcharts tracker fires
        p.mouse.move(bb["x"] + bb["width"] / 2 + dx, bb["y"] + bb["height"] / 2)
        p.wait_for_timeout(300)
    tip = " ".join(p.locator(".highcharts-tooltip").evaluate_all("els => els.map(e => e.textContent)"))
    s.check("composed: shared tooltip lists both series on hover", "2025" in tip and "2026" in tip, tip)
    pt.click()
    p.wait_for_timeout(1000)
    txt = p.locator("p.rt-Text, span.rt-Text").first.inner_text()
    s.check("composed: line point click -> series events.click -> State.on_point_click", "Clicked Mar: 3 units" in p.locator("body").inner_text(), txt)
    p.locator(".highcharts-legend-item").first.click()
    p.wait_for_timeout(800)
    vis = p.locator(".highcharts-series-0").first.get_attribute("visibility")
    s.check("composed: legend click hides the 2025 series", vis == "hidden", vis)
    p.locator(".highcharts-contextbutton").first.click()
    p.wait_for_timeout(600)
    menu = p.locator(".highcharts-menu-item").all_inner_texts()
    s.check("composed: exporting context menu opens with download items", any("PNG" in m for m in menu), menu)
    p.keyboard.press("Escape")
    p.mouse.click(5, 5)
    title_fill0 = p.locator(".highcharts-title").first.evaluate("e => getComputedStyle(e).fill + ' / ' + getComputedStyle(e).color")
    bg0 = p.locator(".highcharts-background").first.evaluate("e => getComputedStyle(e).fill")
    p.locator("button:has(svg.lucide-sun), button:has(svg.lucide-moon)").first.click()
    p.wait_for_timeout(1000)
    title_fill1 = p.locator(".highcharts-title").first.evaluate("e => getComputedStyle(e).fill + ' / ' + getComputedStyle(e).color")
    bg1 = p.locator(".highcharts-background").first.evaluate("e => getComputedStyle(e).fill")
    s.note(f"color mode toggle: title {title_fill0} -> {title_fill1}; background {bg0} -> {bg1}; html class={p.evaluate('document.documentElement.className')}")
    s.check("composed: chart colours follow the color mode toggle", (title_fill0 != title_fill1) or (bg0 != bg1), {"title": [title_fill0, title_fill1], "bg": [bg0, bg1]})
    s.shot(p, "index-after")
    p.reload(wait_until="networkidle")
    p.wait_for_selector(".highcharts-root")
    p.wait_for_timeout(1200)
    s.check("index: State.last_point survives reload", "Clicked Mar: 3 units" in p.locator("body").inner_text())


def qa_page(s, p):
    p.goto(base + "/qa", wait_until="networkidle")
    p.wait_for_selector(".highcharts-root")
    p.wait_for_timeout(1200)
    n = lambda: p.locator(".highcharts-container").nth(0).locator(".highcharts-series-0 .highcharts-point[class*='highcharts-color-']").count()  # noqa: E731
    s.check("qa: line series data from State renders 3 points", n() == 3, n())
    p.click("#qa-push")
    p.wait_for_timeout(1000)
    s.check("qa: pushing to State.data adds a point (4)", n() == 4, n())
    p.click("#qa-retitle")
    p.wait_for_timeout(1000)
    titles = p.locator(".highcharts-title").evaluate_all("els => els.map(e => e.textContent)")
    slices = p.locator(".highcharts-container").nth(1).locator(".highcharts-point[class*='highcharts-color-']").count()
    s.check("qa: title child component + options dict follow State (both retitled, pie 3 slices)", titles == ["QA retitled", "QA retitled"] and slices == 3, {"titles": titles, "slices": slices})
    s.shot(p, "qa-after")
    p.reload(wait_until="networkidle")
    p.wait_for_selector(".highcharts-root")
    p.wait_for_timeout(1500)
    t2 = p.locator(".highcharts-title").evaluate_all("els => els.map(e => e.textContent)")
    s.check("qa: after reload charts show the session state (4 points, retitled)", n() == 4 and t2 == ["QA retitled", "QA retitled"], {"points": n(), "titles": t2})


with Session(f"highcharts-{label}", Path(out)) as s:
    s.note(f"guard: {info['versions']}")
    p = s.new_page(label="hc")
    scenario(s, "index", main_page, s, p)
    scenario(s, "qa", qa_page, s, p)
