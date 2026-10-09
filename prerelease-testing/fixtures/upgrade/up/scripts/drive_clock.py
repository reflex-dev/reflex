"""Drive reflex-examples clock (rx.Cookie zone, bg tick task, on_load reset, radix select).

Usage: drive_clock.py <url> <outdir> <tag> [expect_zone_at_load]
Checks: render, stopped on load, switch starts the background tick, default/initial zone
correct, zone change applies while ticking, zone cookie written, reload keeps the cookie
zone and resets the switch (on_load), switch off stops ticks, fresh context gets defaults.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from clock_common import digital, hour_matches, select_text, zone_cookie  # noqa: E402
from harness import CHROMIUM, Run, guard_driver_python, wait_for  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG = sys.argv[1:4]
EXPECT_ZONE = sys.argv[4] if len(sys.argv) > 4 else "US/Pacific"
run = Run(TAG, OUT)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context()
    page = ctx.new_page()
    run.attach(page)
    page.goto(URL, wait_until="load")
    page.get_by_role("switch").wait_for(timeout=40000)
    wait_for(lambda: len(digital(page)) == 6, 15)
    time.sleep(1.5)
    run.shot(page, "01_initial")
    parts = digital(page)
    run.check("render: switch + select + 6-part digital clock",
              page.get_by_role("switch").count() == 1 and len(parts) == 6, parts)
    s1 = digital(page); time.sleep(2.2); s2 = digital(page)
    run.check("stopped on load (on_load sets running=False)", s1 == s2, f"{s1} -> {s2}")
    run.check(f"initial zone {EXPECT_ZONE} shown in select", select_text(page) == EXPECT_ZONE, select_text(page))
    page.get_by_role("switch").click()
    time.sleep(1.5); t1 = digital(page); time.sleep(2.5); t2 = digital(page)
    run.check("switch on -> background tick task advances seconds", t1 != t2 and len(t2) == 6, f"{t1} -> {t2}")
    run.check(f"time correct for {EXPECT_ZONE}", hour_matches(t2, EXPECT_ZONE), t2)
    run.shot(page, "02_ticking")
    page.get_by_role("combobox").first.click()
    page.get_by_role("option", name="Asia/Tokyo").click()
    ok = wait_for(lambda: hour_matches(digital(page), "Asia/Tokyo"), 6)
    run.check("zone change to Asia/Tokyo applies while ticking", bool(ok), digital(page))
    a = digital(page); time.sleep(2.2); b = digital(page)
    run.check("still ticking after zone change", a != b, f"{a} -> {b}")
    ck = zone_cookie(ctx)
    run.notes["zone_cookie"] = ck
    run.check("rx.Cookie zone written (Asia/Tokyo)", any("Asia" in v for v in ck.values()), ck)
    run.shot(page, "03_tokyo")
    page.reload(wait_until="load")
    page.get_by_role("switch").wait_for(timeout=30000)
    ok = wait_for(lambda: select_text(page) == "Asia/Tokyo", 10)
    run.check("reload: zone cookie sticks (Asia/Tokyo)", bool(ok), select_text(page))
    run.check("reload: switch reset to off by on_load",
              page.get_by_role("switch").get_attribute("data-state") == "unchecked",
              page.get_by_role("switch").get_attribute("data-state"))
    r1 = digital(page); time.sleep(2.2); r2 = digital(page)
    run.check("reload: clock not ticking", r1 == r2, f"{r1} -> {r2}")
    run.check("reload: displayed time is Tokyo (refresh() on load)", hour_matches(r2, "Asia/Tokyo"), r2)
    run.shot(page, "04_after_reload")
    sw = page.get_by_role("switch")
    sw.click(); time.sleep(1.5); sw.click(); time.sleep(1.3)
    x1 = digital(page); time.sleep(2.4); x2 = digital(page)
    run.check("switch off stops the tick loop", x1 == x2, f"{x1} -> {x2}")
    page.get_by_role("combobox").first.click()
    page.get_by_role("option", name="Europe/Paris").click()
    ok = wait_for(lambda: select_text(page) == "Europe/Paris" and hour_matches(digital(page), "Europe/Paris"), 6)
    run.check("zone change while stopped (Europe/Paris)", bool(ok), f"{select_text(page)} {digital(page)}")
    ctx2 = browser.new_context()
    p2 = ctx2.new_page()
    run.attach(p2, "ctx2")
    p2.goto(URL, wait_until="load")
    p2.get_by_role("switch").wait_for(timeout=30000)
    ok = wait_for(lambda: select_text(p2) == "US/Pacific", 10)
    run.check("fresh context: default zone US/Pacific (no cookie)", bool(ok), select_text(p2))
    ctx2.close()
    # leave this context's cookie at Europe/Paris
    run.notes["final_zone_cookie"] = zone_cookie(ctx)
    browser.close()
sys.exit(run.finish())
