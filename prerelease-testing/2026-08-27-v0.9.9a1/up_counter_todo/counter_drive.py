"""Drive the counter example app end-to-end: increment/decrement/randomize/color-mode.

Usage: python counter_drive.py <url> <shot_prefix> <report_json>
"""

import json
import re
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1]
SHOT = sys.argv[2]
REPORT = sys.argv[3]

console_msgs = []
failed_requests = []
bad_responses = []
ws_events = []
steps = []


def step(name, ok, detail=""):
    steps.append({"name": name, "ok": ok, "detail": detail})
    print(f"  step {name}: {'OK' if ok else 'FAIL'} {detail}")


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context()
    page = ctx.new_page()
    page.on("console", lambda m: console_msgs.append((m.type, m.text)))
    page.on("requestfailed", lambda r: failed_requests.append((r.url, str(r.failure))))
    page.on(
        "response",
        lambda r: bad_responses.append((r.status, r.url)) if r.status >= 400 else None,
    )

    def on_ws(ws):
        ws_events.append(("open", ws.url))
        ws.on("close", lambda w: ws_events.append(("close", w.url)))

    page.on("websocket", on_ws)

    page.goto(URL, wait_until="networkidle", timeout=60000)
    heading = page.locator("h1")
    # wait for hydration: heading should show the initial count "0"
    try:
        heading.wait_for(state="visible", timeout=30000)
        page.wait_for_function(
            "document.querySelector('h1') && /^\\d+$/.test(document.querySelector('h1').innerText.trim())",
            timeout=30000,
        )
        initial = heading.inner_text().strip()
        step("initial_render", initial == "0", f"heading={initial!r}")
    except Exception as e:
        step("initial_render", False, repr(e))
    page.screenshot(path=f"{SHOT}-initial.png")

    def wait_count(expected, timeout=10000):
        page.wait_for_function(
            f"document.querySelector('h1').innerText.trim() === '{expected}'",
            timeout=timeout,
        )

    try:
        page.get_by_role("button", name="Increment").click()
        wait_count(1)
        page.get_by_role("button", name="Increment").click()
        wait_count(2)
        step("increment_x2", True, "0 -> 1 -> 2")
    except Exception as e:
        step("increment_x2", False, repr(e))

    try:
        page.get_by_role("button", name="Decrement").click()
        wait_count(1)
        step("decrement", True, "2 -> 1")
    except Exception as e:
        step("decrement", False, repr(e))

    try:
        page.get_by_role("button", name="Randomize").click()
        page.wait_for_function(
            "/^\\d+$/.test(document.querySelector('h1').innerText.trim())",
            timeout=10000,
        )
        page.wait_for_timeout(500)
        val = heading.inner_text().strip()
        ok = bool(re.fullmatch(r"\d+", val)) and 0 <= int(val) <= 100
        step("randomize", ok, f"value={val}")
        rand_val = int(val) if ok else None
    except Exception as e:
        step("randomize", False, repr(e))
        rand_val = None

    if rand_val is not None:
        try:
            page.get_by_role("button", name="Decrement").click()
            wait_count(rand_val - 1)
            step("decrement_after_random", True, f"{rand_val} -> {rand_val - 1}")
        except Exception as e:
            step("decrement_after_random", False, repr(e))

    # negative counts: decrement to below zero from a fresh randomize=... skip; instead
    # test color mode toggle (top-right icon button).
    try:
        before = page.evaluate("document.documentElement.className")
        # the color mode button is the only icon button positioned top-right
        page.locator("button").first.click()
        page.wait_for_timeout(800)
        after = page.evaluate("document.documentElement.className")
        step("color_mode_toggle", before != after, f"{before!r} -> {after!r}")
    except Exception as e:
        step("color_mode_toggle", False, repr(e))
    page.screenshot(path=f"{SHOT}-final.png")

    # reload to check state persistence behavior + hydration second time
    try:
        page.reload(wait_until="networkidle")
        page.wait_for_function(
            "document.querySelector('h1') && /^-?\\d+$/.test(document.querySelector('h1').innerText.trim())",
            timeout=30000,
        )
        val = heading.inner_text().strip()
        step("reload_rehydrate", True, f"heading after reload={val}")
    except Exception as e:
        step("reload_rehydrate", False, repr(e))
    page.screenshot(path=f"{SHOT}-reload.png")
    page.wait_for_timeout(1000)
    browser.close()

report = {
    "url": URL,
    "steps": steps,
    "console": console_msgs,
    "failed_requests": failed_requests,
    "http_4xx_5xx": bad_responses,
    "websockets": ws_events,
}
with open(REPORT, "w") as f:
    json.dump(report, f, indent=2)

print("CONSOLE:")
for t, m in console_msgs:
    print(f"  [{t}] {m[:300]}")
print("FAILED_REQUESTS:", json.dumps(failed_requests, default=str))
print("HTTP_4XX_5XX:", json.dumps(bad_responses))
print("WEBSOCKETS:", json.dumps(ws_events))
print("ALL_STEPS_OK:", all(s["ok"] for s in steps))
