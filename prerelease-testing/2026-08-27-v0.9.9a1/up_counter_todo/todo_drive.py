"""Drive the todo example app end-to-end: add items, check off (=delete), edge cases.

Usage: python todo_drive.py <url> <shot_prefix> <report_json>
"""

import json
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

    def items():
        return page.locator("ol li").evaluate_all(
            "els => els.map(e => e.querySelector('span') ? e.querySelector('span').innerText.trim() : e.innerText.trim())"
        )

    def wait_items(expected, timeout=10000):
        page.wait_for_function(
            "exp => JSON.stringify(Array.from(document.querySelectorAll('ol li')).map("
            "e => (e.querySelector('span')||e).innerText.trim())) === JSON.stringify(exp)",
            arg=expected,
            timeout=timeout,
        )

    page.goto(URL, wait_until="networkidle", timeout=60000)
    initial_expected = ["Write Code", "Sleep", "Have Fun"]
    try:
        wait_items(initial_expected, timeout=30000)
        step("initial_render", True, f"items={items()}")
    except Exception as e:
        step("initial_render", False, f"items={items()} err={e!r}")
    page.screenshot(path=f"{SHOT}-initial.png")

    inp = page.get_by_placeholder("Add a todo...")

    # add via Add button
    try:
        inp.fill("Buy milk")
        page.get_by_role("button", name="Add").click()
        wait_items([*initial_expected, "Buy milk"])
        input_val = inp.input_value()
        step(
            "add_item_button",
            input_val == "",
            f"items={items()} input_after={input_val!r} (reset_on_submit)",
        )
    except Exception as e:
        step("add_item_button", False, f"items={items()} err={e!r}")

    # add via Enter key
    try:
        inp.fill("Walk dog")
        inp.press("Enter")
        wait_items([*initial_expected, "Buy milk", "Walk dog"])
        step("add_item_enter", True, f"items={items()}")
    except Exception as e:
        step("add_item_enter", False, f"items={items()} err={e!r}")

    # empty submit should be a no-op
    try:
        before = items()
        page.get_by_role("button", name="Add").click()
        page.wait_for_timeout(1500)
        after = items()
        step("empty_submit_noop", before == after, f"before={before} after={after}")
    except Exception as e:
        step("empty_submit_noop", False, repr(e))

    # special characters survive round-trip unescaped
    try:
        special = "Café <b>&amp;</b> 50%"
        inp.fill(special)
        inp.press("Enter")
        wait_items([*initial_expected, "Buy milk", "Walk dog", special])
        step("add_item_special_chars", True, f"items={items()}")
    except Exception as e:
        step("add_item_special_chars", False, f"items={items()} err={e!r}")
    page.screenshot(path=f"{SHOT}-added.png")

    # check off (finish = remove) the middle initial item
    try:
        li = page.locator("ol li", has_text="Sleep")
        li.locator("button").click()
        wait_items(
            ["Write Code", "Have Fun", "Buy milk", "Walk dog", "Café <b>&amp;</b> 50%"]
        )
        step("finish_middle_item", True, f"items={items()}")
    except Exception as e:
        step("finish_middle_item", False, f"items={items()} err={e!r}")

    # check off the first item
    try:
        page.locator("ol li", has_text="Write Code").locator("button").click()
        wait_items(["Have Fun", "Buy milk", "Walk dog", "Café <b>&amp;</b> 50%"])
        step("finish_first_item", True, f"items={items()}")
    except Exception as e:
        step("finish_first_item", False, f"items={items()} err={e!r}")
    page.screenshot(path=f"{SHOT}-after-finish.png")

    # reload: record whether state persists for the same tab token
    try:
        pre = items()
        page.reload(wait_until="networkidle")
        page.wait_for_function(
            "document.querySelectorAll('ol li').length > 0", timeout=30000
        )
        page.wait_for_timeout(1000)
        post = items()
        step("reload_state", True, f"pre={pre} post={post} persisted={pre == post}")
    except Exception as e:
        step("reload_state", False, repr(e))
    page.screenshot(path=f"{SHOT}-reload.png")
    page.wait_for_timeout(500)
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
