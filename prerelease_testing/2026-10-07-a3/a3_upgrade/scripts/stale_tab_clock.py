"""Keep ONE clock tab open across a server stop -> in-place upgrade -> restart.

Usage: stale_tab_clock.py <url> <outdir> <tag> <ctldir>
Control files in <ctldir> (created by the operator): `down` after the old server is
stopped, `up` once the new version is serving. This script writes `ready` once the tab
is set up (zone Europe/Paris, clock ticking) and `done` at the end.
Records whether the page reloaded by itself (window marker), what the user sees while
the server is down / after it returns, whether the old JS can still drive the new
backend (switch + zone change), and whether the zone cookie survives a manual reload.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from clock_common import digital, hour_matches, select_text, zone_cookie  # noqa: E402
from harness import CHROMIUM, Run, guard_driver_python, wait_for  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
URL, OUT, TAG, CTL = sys.argv[1:5]
CTL = Path(CTL)
CTL.mkdir(parents=True, exist_ok=True)
run = Run(TAG, OUT)


def wait_file(page, name, timeout=3600):
    # page.wait_for_timeout keeps Playwright's event loop pumping, so console/ws
    # events are timestamped when they happen (time.sleep would batch them).
    end = time.time() + timeout
    while time.time() < end:
        if (CTL / name).exists():
            return True
        page.wait_for_timeout(500)
    return False


def snapshot(page, label):
    info = {
        "marker": page.evaluate("() => window.__qa_marker || null"),
        "select": select_text(page) if page.get_by_role("combobox").count() else None,
        "digital": digital(page),
        "switch": page.get_by_role("switch").get_attribute("data-state") if page.get_by_role("switch").count() else None,
        "body_tail": page.inner_text("body")[-400:],
        "toasts": page.locator("[data-sonner-toast]").all_inner_texts(),
        "url": page.url,
    }
    run.notes[label] = info
    run.shot(page, label)
    print(label, info, flush=True)
    return info


def ticking(page, wait=2.4):
    a = digital(page); page.wait_for_timeout(int(wait * 1000)); b = digital(page)
    return a != b, a, b


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context()
    page = ctx.new_page()
    run.attach(page)
    page.goto(URL, wait_until="load")
    page.get_by_role("switch").wait_for(timeout=60000)
    wait_for(lambda: len(digital(page)) == 6, 15)
    page.evaluate("() => { window.__qa_marker = 'old-tab-' + Date.now(); }")
    page.get_by_role("combobox").first.click()
    page.get_by_role("option", name="Europe/Paris").click()
    wait_for(lambda: select_text(page) == "Europe/Paris", 6)
    page.get_by_role("switch").click()
    tk, a, b = ticking(page)
    run.check("A: old version tab set up (Europe/Paris, ticking)", tk and hour_matches(b, "Europe/Paris"), f"{a}->{b}")
    run.notes["A_cookie"] = zone_cookie(ctx)
    snapshot(page, "A_before")
    (CTL / "ready").write_text("1")
    print("READY; waiting for 'down'", flush=True)
    wait_file(page, "down")
    page.wait_for_timeout(8000)
    snapshot(page, "B_server_down")
    print("waiting for 'up'", flush=True)
    wait_file(page, "up")
    t_up = run._t()
    run.notes["t_up"] = t_up
    page.wait_for_timeout(25000)
    info = snapshot(page, "C_after_up")
    reloaded = info["marker"] is None
    run.check("C: did the old tab reload itself after the new server came up?", "anomaly" if not reloaded else "pass",
              f"marker={'gone (page reloaded)' if reloaded else info['marker']}")
    tk, a, b = ticking(page)
    run.notes["C_ticking"] = [tk, a, b]
    run.check("C: clock state after reconnect (was ticking before upgrade)", "pass", f"ticking={tk} {a}->{b}")
    # interact with whatever frontend is loaded now
    try:
        page.get_by_role("combobox").first.click(timeout=5000)
        page.get_by_role("option", name="Asia/Tokyo").click(timeout=5000)
        ok = wait_for(lambda: hour_matches(digital(page), "Asia/Tokyo"), 8)
        run.check("D: zone change from the (possibly stale) tab reaches the new backend", bool(ok), digital(page))
    except Exception as e:  # noqa: BLE001
        run.check("D: zone change from the (possibly stale) tab reaches the new backend", False, e)
    sw_before = page.get_by_role("switch").get_attribute("data-state")
    page.get_by_role("switch").click()
    page.wait_for_timeout(1500)
    tk2, a2, b2 = ticking(page)
    run.check("D: switch toggle from the tab drives the bg task on the new backend", "pass" if tk2 != tk else "fail",
              f"switch {sw_before}->{page.get_by_role('switch').get_attribute('data-state')} ticking {tk}->{tk2}")
    run.notes["D_cookie"] = zone_cookie(ctx)
    snapshot(page, "D_interact")
    page.reload(wait_until="load")
    page.get_by_role("switch").wait_for(timeout=30000)
    wait_for(lambda: len(digital(page)) == 6, 10)
    page.wait_for_timeout(2000)
    info = snapshot(page, "E_after_manual_reload")
    expect = "Asia/Tokyo" if run.notes["D_cookie"] and any("Asia" in v for v in run.notes["D_cookie"].values()) else "Europe/Paris"
    run.check("E: zone cookie survives the upgrade in the same browser session", info["select"] == expect,
              f"select={info['select']} expected={expect} cookie={zone_cookie(ctx)}")
    run.check("E: on_load reset switch to off after reload", info["switch"] == "unchecked", info["switch"])
    browser.close()
(CTL / "done").write_text("1")
sys.exit(run.finish())
