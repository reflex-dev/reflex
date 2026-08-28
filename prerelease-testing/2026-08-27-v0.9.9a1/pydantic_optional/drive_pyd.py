"""Drive the pydantic v2 app end-to-end in Chromium (works on 0.9.8 and 0.9.9a1)."""

import json
import sys

from playwright.sync_api import expect, sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3301/"
SHOT_PREFIX = sys.argv[2] if len(sys.argv) > 2 else "pyd"

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
    expect(page.locator("#title")).to_have_text("pydantic v2 app", timeout=30000)

    expect(page.locator("#user-name")).to_have_text("Ada")
    expect(page.locator("#user-age")).to_have_text("36")
    expect(page.locator("#user-city")).to_have_text("Zurich")
    results["initial_render"] = "ok"

    # computed var serializing the model
    uj = page.locator("#user-json").inner_text()
    parsed = json.loads(uj)
    assert parsed["name"] == "Ada" and parsed["address"]["city"] == "Zurich", uj
    results["computed_var_model_dump_json"] = "ok"
    page.screenshot(path=f"{SHOT_PREFIX}_initial.png")

    # top-level model field mutation
    page.click("#bump-age")
    expect(page.locator("#user-age")).to_have_text("37", timeout=10000)
    results["model_field_mutation"] = "ok"

    # nested model field mutation
    page.fill("#city-input", "Basel")
    expect(page.locator("#user-city")).to_have_text("Basel", timeout=10000)
    results["nested_model_mutation"] = "ok"

    # list inside model
    page.click("#add-tag")
    expect(page.locator("#user-tags")).to_have_text("tag-0", timeout=10000)
    page.click("#add-tag")
    expect(page.locator("#user-tags")).to_have_text("tag-0,tag-1", timeout=10000)
    results["list_in_model_mutation"] = "ok"

    # computed var reflects mutations
    uj2 = json.loads(page.locator("#user-json").inner_text())
    assert uj2["age"] == 37 and uj2["address"]["city"] == "Basel", uj2
    assert uj2["tags"] == ["tag-0", "tag-1"], uj2
    results["computed_var_after_mutation"] = "ok"

    # foreach over list[Model] + append
    labels = page.locator(".item-label")
    expect(labels).to_have_count(2, timeout=10000)
    qtys = page.locator(".item-qty")
    expect(qtys.nth(1)).to_have_text("2")
    page.click("#add-item")
    expect(labels).to_have_count(3, timeout=10000)
    expect(labels.nth(2)).to_have_text("item-2")
    results["foreach_model_append"] = "ok"

    # event handler with model-hinted arg receiving a dict payload
    page.click("#send-user")
    expect(page.locator("#received")).to_have_text("Grace:45:Paris:User", timeout=10000)
    results["model_event_arg_validate"] = "ok"

    page.screenshot(path=f"{SHOT_PREFIX}_final.png")
    browser.close()

print("RESULTS:", json.dumps(results, indent=1))
print("CONSOLE:")
for t, m in console_msgs:
    flag = "" if any(b in m for b in BENIGN) else "  <-- UNEXPECTED" if t in ("error", "warning") else ""
    print(f"  [{t}] {m[:300]}{flag}")
print("FAILED_REQUESTS:", json.dumps(failed_requests, default=str))
print("HTTP_4XX_5XX:", json.dumps(bad_responses))
