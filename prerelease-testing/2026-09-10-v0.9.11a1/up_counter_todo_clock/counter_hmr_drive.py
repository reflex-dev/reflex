"""Hot-reload check for the counter app (#7071: providers survive hot updates).

Usage: python counter_hmr_drive.py <url> <app_py_path> <shot_prefix> <report_json>

Loads the page, increments to 3, then edits the app source (button label
"Increment" -> "Increment!") while the page is open and checks that the new label
appears WITHOUT a full reload, that the count (state) survived, how many
/_event websocket connections were opened, and that the console stayed clean.
Reverts the edit at the end.
"""

import sys
import time

from drive_common import run

APP_PY = sys.argv[2]
sys.argv = [sys.argv[0], sys.argv[1], sys.argv[3], sys.argv[4]]


def driver(page, cap):
    src = open(APP_PY).read()
    assert '"Increment",' in src, "unexpected counter.py content"
    page.goto(cap.url, wait_until="networkidle", timeout=60000)
    page.wait_for_function(
        "document.querySelector('h1') && /^\\d+$/.test(document.querySelector('h1').innerText.trim())",
        timeout=30000,
    )
    page.evaluate("window.__hmr_marker = 'alive'")
    btn = page.get_by_role("button", name="Increment", exact=True)
    for _ in range(3):
        btn.click()
    page.wait_for_function("document.querySelector('h1').innerText.trim() === '3'", timeout=10000)
    cap.step("pre_edit_count_3", True, "count=3, marker set")
    ws_before = len([e for e in cap.ws_events if e[0] == "open" and "_event" in e[1]])
    page.screenshot(path=f"{cap.shot}-before-edit.png")

    t0 = time.time()
    open(APP_PY, "w").write(src.replace('"Increment",', '"Increment!",', 1))
    try:
        page.get_by_role("button", name="Increment!", exact=True).wait_for(timeout=60000)
        dt = time.time() - t0
        cap.step("hot_update_applied", True, f"new label visible after {dt:.1f}s")
    except Exception as e:
        cap.step("hot_update_applied", False, repr(e))
    page.wait_for_timeout(2500)
    marker = page.evaluate("window.__hmr_marker || null")
    count = page.locator("h1").inner_text().strip()
    ws_after = len([e for e in cap.ws_events if e[0] == "open" and "_event" in e[1]])
    cap.step("no_full_reload", marker == "alive", f"window marker={marker!r} (None => page fully reloaded)")
    cap.step("state_survived_hot_update", count == "3", f"count after edit={count!r}")
    cap.step("event_socket_connections", True, f"/_event sockets opened before={ws_before} after={ws_after} (extra opens = reconnects)")
    # the app must still be interactive after the hot update
    try:
        page.get_by_role("button", name="Increment!", exact=True).click()
        page.wait_for_function("document.querySelector('h1').innerText.trim() === '4'", timeout=10000)
        cap.step("interactive_after_hot_update", True, "3 -> 4")
    except Exception as e:
        cap.step("interactive_after_hot_update", False, f"count={page.locator('h1').inner_text()!r} {e!r}")
    page.screenshot(path=f"{cap.shot}-after-edit.png")
    open(APP_PY, "w").write(src)  # revert
    page.wait_for_timeout(4000)  # let the revert recompile settle


run(driver)
