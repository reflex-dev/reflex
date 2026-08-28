"""Playwright driver for the reflex-enterprise mantine demo.

Usage: python drive_mantine.py <base_url> <shots_dir>
Exercises: index links, /dates pickers + toast, /pill remove + toast,
/tags-input add tag, Source tab, demo dropdown navigation.
Prints CONSOLE/PAGEERROR/REQFAIL lines and a RESULT line per check.
"""

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1].rstrip("/")
SHOTS = Path(sys.argv[2])
SHOTS.mkdir(parents=True, exist_ok=True)

results = []
console_lines = []
page_errors = []
req_failures = []

BENIGN_SNIPPETS = (
    "HydrateFallback",
    "[vite] connecting",
    "[vite] connected",
    "React DevTools",
    "Download the React DevTools",
)


def check(name, ok, details=""):
    results.append({"name": name, "ok": bool(ok), "details": details})
    print(f"RESULT {'PASS' if ok else 'FAIL'} {name} :: {details}")


def snap(page, name):
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.on(
        "console",
        lambda m: console_lines.append(f"{m.type}: {m.text}"),
    )
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on(
        "requestfailed",
        lambda r: req_failures.append(f"{r.method} {r.url} :: {r.failure}"),
    )
    page.on(
        "response",
        lambda r: req_failures.append(f"HTTP{r.status} {r.url}")
        if r.status >= 400
        else None,
    )

    # 1. index
    page.goto(BASE + "/", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)
    snap(page, "01_index")
    links = page.locator("a[href='/dates'], a[href='/pill'], a[href='/tags-input']")
    check("index_renders_links", links.count() >= 3, f"count={links.count()}")

    # 2. /dates
    page.goto(BASE + "/dates", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    snap(page, "02_dates")
    # calendar renders day cells
    days = page.locator("table.m_395412a6 button, .mantine-Calendar-day, [data-mantine-stop-propagation], button.m_396ce5cb")
    day_count = page.locator("button.mantine-DatePicker-day, .m_396ce5cb").count()
    check("dates_calendar_renders", day_count > 20, f"day-cells={day_count}")
    # click a day in the DatePicker (3rd card) -> toast "Date selected:"
    picker_days = page.locator(".mantine-DatePicker-day")
    if picker_days.count() == 0:
        picker_days = page.locator("button.m_396ce5cb")
    try:
        picker_days.nth(10).click(timeout=5000)
        page.wait_for_timeout(1500)
        toast = page.locator("text=/Date selected:/").first
        ok = toast.is_visible()
        snap(page, "03_dates_toast")
        check("dates_datepicker_click_toast", ok, "toast 'Date selected:' visible" if ok else "no toast")
    except Exception as e:
        snap(page, "03_dates_toast_fail")
        check("dates_datepicker_click_toast", False, f"exception: {e}")

    # TimeInput on_change -> toast "Time selected"
    try:
        ti = page.locator("input[type='time']").first
        ti.fill("13:37")
        page.wait_for_timeout(1500)
        ok = page.locator("text=/Time selected:/").first.is_visible()
        snap(page, "04_dates_time_toast")
        check("dates_timeinput_toast", ok, "toast visible" if ok else "no toast")
    except Exception as e:
        check("dates_timeinput_toast", False, f"exception: {e}")

    # 3. /pill
    page.goto(BASE + "/pill", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)
    snap(page, "05_pill")
    pills = page.locator("text=Default")
    check("pill_renders", pills.count() >= 7, f"pill-count={pills.count()}")
    try:
        rm = page.locator(".mantine-Pill-remove, button[class*='remove' i]").first
        rm.click(timeout=5000)
        page.wait_for_timeout(1500)
        ok = page.locator("text=Removed").first.is_visible()
        snap(page, "06_pill_removed_toast")
        check("pill_remove_toast", ok, "toast 'Removed' visible" if ok else "no toast")
    except Exception as e:
        snap(page, "06_pill_removed_fail")
        check("pill_remove_toast", False, f"exception: {e}")

    # Source tab on /pill
    try:
        page.locator("text=Source").first.click(timeout=5000)
        page.wait_for_timeout(1500)
        ok = page.locator("code, pre").first.is_visible()
        snap(page, "07_pill_source_tab")
        check("pill_source_tab", ok, "code block visible" if ok else "no code block")
    except Exception as e:
        check("pill_source_tab", False, f"exception: {e}")

    # 4. /tags-input
    page.goto(BASE + "/tags-input", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(2000)
    snap(page, "08_tags_input")
    t1 = page.locator("text=Tag1").first
    check("tags_initial_render", t1.is_visible(), "Tag1 visible" if t1.is_visible() else "Tag1 missing")
    try:
        inp = page.locator("input[placeholder='Enter tags']").first
        inp.click()
        inp.type("playwright-tag")
        inp.press("Enter")
        page.wait_for_timeout(2000)
        ok = page.locator("text=playwright-tag").first.is_visible()
        snap(page, "09_tags_added")
        check("tags_add_roundtrip", ok, "new tag chip visible" if ok else "chip missing")
        # remove Tag1 via its remove button, verify state updates
        page.locator(".mantine-TagsInput-pill, .mantine-Pill-root").first.locator("button").first.click(timeout=5000)
        page.wait_for_timeout(2000)
        gone = page.locator("text=Tag1").count() == 0
        snap(page, "10_tags_removed")
        check("tags_remove_roundtrip", gone, "Tag1 removed" if gone else "Tag1 still present")
    except Exception as e:
        snap(page, "09_tags_fail")
        check("tags_add_roundtrip", False, f"exception: {e}")

    # 5. demo dropdown navigation (on /tags-input, pick Dates)
    try:
        page.locator("button[role='combobox'], .rt-SelectTrigger").first.click(timeout=5000)
        page.wait_for_timeout(800)
        page.locator("[role='option']", has_text="Dates").first.click(timeout=5000)
        page.wait_for_url("**/dates", timeout=10000)
        snap(page, "11_dropdown_nav")
        check("dropdown_navigation", True, f"navigated to {page.url}")
    except Exception as e:
        snap(page, "11_dropdown_nav_fail")
        check("dropdown_navigation", False, f"exception: {e}")

    browser.close()

interesting_console = [
    line
    for line in console_lines
    if not any(s in line for s in BENIGN_SNIPPETS)
    and line.split(":", 1)[0] in ("error", "warning")
]
print("\n=== CONSOLE (error/warning, non-benign) ===")
for line in interesting_console:
    print("CONSOLE", line)
print("=== PAGE ERRORS ===")
for e in page_errors:
    print("PAGEERROR", e)
print("=== REQUEST FAILURES / 4xx-5xx ===")
for r in req_failures:
    print("REQFAIL", r)

(SHOTS / "results.json").write_text(
    json.dumps(
        {
            "results": results,
            "console_all": console_lines,
            "page_errors": page_errors,
            "req_failures": req_failures,
        },
        indent=2,
    )
)
fails = [r for r in results if not r["ok"]]
print(f"\nSUMMARY: {len(results) - len(fails)}/{len(results)} passed")
