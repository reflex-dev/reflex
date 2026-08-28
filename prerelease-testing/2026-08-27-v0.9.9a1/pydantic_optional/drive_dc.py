"""Drive the dataclass/dict app (no pydantic installed) end-to-end in Chromium."""

import json
import sys

from playwright.sync_api import expect, sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3300/"
SHOT_PREFIX = sys.argv[2] if len(sys.argv) > 2 else "dc"

console_msgs = []
failed_requests = []
bad_responses = []

BENIGN = ("HydrateFallback", "[vite] connecting", "[vite] connected", "React DevTools")

results = {}

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
    page.goto(URL, wait_until="networkidle", timeout=60000)
    expect(page.locator("#title")).to_have_text("dataclass/dict app", timeout=30000)

    # initial values
    expect(page.locator("#profile-name")).to_have_text("Ada")
    expect(page.locator("#profile-age")).to_have_text("36")
    expect(page.locator("#theme")).to_have_text("light")
    results["initial_render"] = "ok"
    page.screenshot(path=f"{SHOT_PREFIX}_initial.png")

    # dataclass field mutation
    page.click("#bump-age")
    expect(page.locator("#profile-age")).to_have_text("37", timeout=10000)
    page.click("#bump-age")
    expect(page.locator("#profile-age")).to_have_text("38", timeout=10000)
    results["dataclass_mutation"] = "ok"

    # input -> dataclass str field
    page.fill("#name-input", "Marge")
    expect(page.locator("#profile-name")).to_have_text("Marge", timeout=10000)
    results["dataclass_set_name"] = "ok"

    # dict mutation
    page.click("#toggle-theme")
    expect(page.locator("#theme")).to_have_text("dark", timeout=10000)
    page.click("#toggle-theme")
    expect(page.locator("#theme")).to_have_text("light", timeout=10000)
    results["dict_mutation"] = "ok"

    # foreach over list of dataclasses + append
    labels = page.locator(".todo-label")
    expect(labels).to_have_count(2, timeout=10000)
    page.click("#add-todo")
    expect(labels).to_have_count(3, timeout=10000)
    expect(labels.nth(2)).to_have_text("todo-2")
    results["foreach_dataclass_append"] = "ok"

    # event handler with dataclass-hinted arg receiving a dict payload
    page.click("#send-profile")
    expect(page.locator("#last-event-arg")).to_have_text(
        "Grace:45:Profile", timeout=10000
    )
    results["dataclass_event_arg"] = "ok"

    page.screenshot(path=f"{SHOT_PREFIX}_final.png")
    browser.close()

print("RESULTS:", json.dumps(results, indent=1))
print("CONSOLE:")
for t, m in console_msgs:
    flag = "" if any(b in m for b in BENIGN) else "  <-- UNEXPECTED" if t in ("error", "warning") else ""
    print(f"  [{t}] {m[:300]}{flag}")
print("FAILED_REQUESTS:", json.dumps(failed_requests, default=str))
print("HTTP_4XX_5XX:", json.dumps(bad_responses))
