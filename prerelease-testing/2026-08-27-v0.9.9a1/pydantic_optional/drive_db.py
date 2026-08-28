"""Drive the sqlmodel CRUD app end-to-end in Chromium."""

import json
import sys

from playwright.sync_api import expect, sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3303/"
SHOT_PREFIX = sys.argv[2] if len(sys.argv) > 2 else "db"

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
    expect(page.locator("#title")).to_have_text("db crud app", timeout=30000)
    expect(page.locator("#status")).to_have_text("loaded 0", timeout=15000)
    results["initial_load_empty"] = "ok"
    page.screenshot(path=f"{SHOT_PREFIX}_initial.png")

    # CREATE
    page.fill("#name", "alice")
    page.fill("#email", "alice@example.com")
    page.click("#add-btn")
    expect(page.locator("#status")).to_have_text("loaded 1", timeout=10000)
    expect(page.locator(".contact-name")).to_have_text("alice")
    page.fill("#name", "bob")
    page.fill("#email", "bob@example.com")
    page.click("#add-btn")
    expect(page.locator("#status")).to_have_text("loaded 2", timeout=10000)
    names = page.locator(".contact-name")
    expect(names).to_have_count(2)
    results["create"] = "ok"

    # UPDATE
    page.click("#rename-btn")
    expect(names.nth(0)).to_have_text("alice-renamed", timeout=10000)
    results["update"] = "ok"

    # DELETE
    page.click("#delete-btn")
    expect(names).to_have_count(1, timeout=10000)
    expect(names.nth(0)).to_have_text("bob")
    results["delete"] = "ok"

    # persistence across reload
    page.reload(wait_until="networkidle")
    expect(page.locator("#status")).to_have_text("loaded 1", timeout=20000)
    expect(page.locator(".contact-name")).to_have_text("bob")
    results["persistence_after_reload"] = "ok"

    page.screenshot(path=f"{SHOT_PREFIX}_final.png")
    browser.close()

print("RESULTS:", json.dumps(results, indent=1))
print("CONSOLE:")
for t, m in console_msgs:
    flag = "" if any(b in m for b in BENIGN) else "  <-- UNEXPECTED" if t in ("error", "warning") else ""
    print(f"  [{t}] {m[:300]}{flag}")
print("FAILED_REQUESTS:", json.dumps(failed_requests, default=str))
print("HTTP_4XX_5XX:", json.dumps(bad_responses))
