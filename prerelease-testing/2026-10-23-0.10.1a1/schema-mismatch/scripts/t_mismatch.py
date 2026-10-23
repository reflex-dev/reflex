"""Prod schema mismatch: old frontend (port FE) against new backend (port BE).

Usage: t_mismatch.py <frontend_url> <report.json> <shots_prefix> [--expect mismatch|match] [--cooldown-wait SECONDS]

Checks: CONNECT auth carries state_schema; state_mismatch received; exactly one
automatic reload; banner on the second mismatch; banner Reload button works;
after the cooldown a fresh navigation reloads again.
"""
import sys
import time

from pwlib import Capture, browser, sync_playwright

url, report, shots = sys.argv[1:4]
expect = "mismatch"
cooldown_wait = 0.0
args = sys.argv[4:]
if "--expect" in args:
    expect = args[args.index("--expect") + 1]
if "--cooldown-wait" in args:
    cooldown_wait = float(args[args.index("--cooldown-wait") + 1])

BANNER = "#reflex-new-version-banner"
results = {}
with sync_playwright() as p:
    b = browser(p)
    page = b.new_page()
    cap = Capture(page)
    page.goto(url)
    page.wait_for_timeout(4000)
    page.screenshot(path=f"{shots}_1_after_load.png")
    connects = [f for f in cap.ws if f["event"] == "sent" and f["payload"].startswith("40")]
    results["connect_frames"] = connects
    results["connect_has_state_schema"] = all('"state_schema"' in f["payload"] for f in connects) and bool(connects)
    mismatch_frames = [f for f in cap.ws if f["event"] == "recv" and "state_mismatch" in f["payload"]]
    results["mismatch_frames"] = mismatch_frames
    results["loads"] = list(cap.loads)
    results["banner_visible_after_load"] = page.locator(BANNER).count() > 0
    results["banner_text"] = page.locator(BANNER).inner_text() if results["banner_visible_after_load"] else None
    results["last_reloaded_key"] = page.evaluate("window.sessionStorage.getItem('reflex_last_reloaded_on_error')")
    # the app must keep working under the banner
    page.click("#inc")
    page.wait_for_timeout(800)
    results["count_after_click"] = page.locator("#count").inner_text()
    if results["banner_visible_after_load"]:
        n_loads = len(cap.loads)
        page.click(f"{BANNER} button")
        page.wait_for_timeout(4000)
        page.screenshot(path=f"{shots}_2_after_banner_reload.png")
        results["loads_after_banner_click"] = len(cap.loads) - n_loads
        results["banner_visible_after_banner_reload"] = page.locator(BANNER).count() > 0
    if cooldown_wait:
        time.sleep(cooldown_wait)
        n_loads = len(cap.loads)
        page.goto(url)
        page.wait_for_timeout(4000)
        page.screenshot(path=f"{shots}_3_after_cooldown.png")
        results["loads_after_cooldown_nav"] = len(cap.loads) - n_loads  # 2 = navigation + auto reload
        results["banner_after_cooldown_nav"] = page.locator(BANNER).count() > 0
    results["anomalies"] = cap.anomalies()
    cap.dump(report, results=results)
    b.close()

for k, v in results.items():
    if k not in ("connect_frames", "mismatch_frames"):
        print(k, "=", v)
print("n_connect_frames", len(results["connect_frames"]), "n_mismatch_frames", len(results["mismatch_frames"]))
ok = results["connect_has_state_schema"]
if expect == "mismatch":
    ok = ok and results["mismatch_frames"] and results["banner_visible_after_load"] and len(results["loads"]) == 2
elif expect == "devwarn":
    warned = any("built for another version" in a for a in results["anomalies"])
    ok = ok and results["mismatch_frames"] and warned and not results["banner_visible_after_load"] and len(results["loads"]) == 1
else:
    ok = ok and not results["mismatch_frames"] and not results["banner_visible_after_load"] and len(results["loads"]) == 1
print("RESULT", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
