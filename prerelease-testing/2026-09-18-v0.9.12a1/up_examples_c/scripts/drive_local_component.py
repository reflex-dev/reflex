"""Drive the reflex-examples `local-component` app end to end.

Flows: local React component render, right-click caps toggle + event passthrough,
popover open/type/live-update, form submit, revert-on-close, rx.scroll_to via id
(forwardRef), color mode toggle.

usage: drive_local_component.py <frontend_url> <label> <shots_dir>
"""

import json
import sys
import time

from playwright.sync_api import sync_playwright

URL = sys.argv[1]
LABEL = sys.argv[2]
SHOTS = sys.argv[3]

console: list[dict] = []
page_errors: list[str] = []
failed: list[str] = []
bad_responses: list[str] = []
results: dict[str, object] = {}


def record(page):
    page.on(
        "console",
        lambda m: console.append({"type": m.type, "text": m.text, "loc": str(m.location)}),
    )
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.on("requestfailed", lambda r: failed.append(f"{r.method} {r.url} :: {r.failure}"))
    page.on(
        "response",
        lambda r: bad_responses.append(f"{r.status} {r.request.method} {r.url}")
        if r.status >= 400
        else None,
    )


def shot(page, name):
    page.screenshot(path=f"{SHOTS}/{LABEL}_{name}.png", full_page=False)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    record(page)

    page.goto(URL, wait_until="networkidle", timeout=90_000)
    page.wait_for_timeout(2500)

    greeting = page.locator("#greeting")
    results["greeting_count"] = greeting.count()
    # 1. initial render of the LOCAL react component
    h1 = greeting.locator("h1")
    results["initial_text"] = h1.inner_text() if h1.count() else None
    # id must reach the DOM (forwardRef through auto-memo, #6850)
    results["greeting_has_id"] = greeting.count() == 1
    # background_color prop must be passed through to the div
    results["greeting_bg"] = greeting.evaluate(
        "el => getComputedStyle(el).backgroundColor"
    ) if greeting.count() else None
    results["greeting_title_attr"] = greeting.get_attribute("title") if greeting.count() else None
    shot(page, "01_initial")

    # 2. right-click -> local useState caps toggle + reflex console_log passthrough
    n_console_before = len(console)
    h1.click(button="right")
    page.wait_for_timeout(900)
    results["after_rightclick_text"] = h1.inner_text()
    results["passthrough_logged"] = any(
        "Yes we pass events through" in c["text"] for c in console[n_console_before:]
    )
    shot(page, "02_rightclick_caps")
    # toggle back
    h1.click(button="right")
    page.wait_for_timeout(600)
    results["after_rightclick2_text"] = h1.inner_text()

    # 3. left-click opens the popover (State.open round trip)
    h1.click()
    page.wait_for_timeout(1200)
    popover_input = page.locator("input[name='who']")
    results["popover_opened"] = popover_input.count() > 0 and popover_input.is_visible()
    shot(page, "03_popover_open")

    # 4. typing updates State.who -> greeting text live
    if results["popover_opened"]:
        popover_input.fill("")
        popover_input.type("Reflex QA", delay=45)
        page.wait_for_timeout(1500)
        results["text_while_typing"] = h1.inner_text()
        shot(page, "04_typed")

        # 5. submit the form -> saved_value set, popover closes
        popover_input.press("Enter")
        page.wait_for_timeout(1500)
        results["after_submit_text"] = h1.inner_text()
        results["popover_closed_after_submit"] = page.locator(
            "input[name='who']"
        ).count() == 0 or not page.locator("input[name='who']").is_visible()
        shot(page, "05_after_submit")

        # 6. reopen, type, press Escape -> revert to saved_value
        h1.click()
        page.wait_for_timeout(1000)
        pi = page.locator("input[name='who']")
        if pi.count() and pi.is_visible():
            pi.fill("")
            pi.type("THROWAWAY", delay=30)
            page.wait_for_timeout(1000)
            results["text_before_escape"] = h1.inner_text()
            page.keyboard.press("Escape")
            page.wait_for_timeout(1500)
            results["after_escape_text"] = h1.inner_text()
            results["reverted_ok"] = results["after_escape_text"] == results["after_submit_text"]
            shot(page, "06_after_escape")
        else:
            results["reopen_failed"] = True

    # 7. rx.scroll_to("greeting") - needs the id on the real DOM node
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(800)
    y_before = page.evaluate("window.scrollY")
    btn = page.get_by_role("button", name="Scroll to Greeting")
    results["scroll_button_found"] = btn.count() > 0
    if btn.count():
        btn.click()
        page.wait_for_timeout(1800)
        y_after = page.evaluate("window.scrollY")
        results["scroll_y_before"] = y_before
        results["scroll_y_after"] = y_after
        results["scroll_worked"] = y_after < y_before - 100
        shot(page, "07_after_scroll_to")

    # 8. color mode toggle -> background_color rx.color_mode_cond
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(500)
    bg_before = page.locator("#greeting").evaluate("el => getComputedStyle(el).backgroundColor")
    cm = page.locator("button.rt-BaseButton").first
    # color_mode.button is positioned top-right; find by its svg-bearing button
    cm_buttons = page.locator("button:has(svg)")
    clicked = False
    for i in range(cm_buttons.count()):
        b = cm_buttons.nth(i)
        try:
            if b.is_visible():
                b.click()
                clicked = True
                break
        except Exception:
            continue
    page.wait_for_timeout(1500)
    bg_after = page.locator("#greeting").evaluate("el => getComputedStyle(el).backgroundColor")
    results["color_mode_clicked"] = clicked
    results["bg_before_colormode"] = bg_before
    results["bg_after_colormode"] = bg_after
    results["color_mode_changed_bg"] = bg_before != bg_after
    shot(page, "08_color_mode")

    # 9. full reload -> hydration still clean, state persists per-session
    page.reload(wait_until="networkidle", timeout=60_000)
    page.wait_for_timeout(2500)
    results["after_reload_text"] = page.locator("#greeting h1").inner_text()
    results["after_reload_has_id"] = page.locator("#greeting").count() == 1
    shot(page, "09_after_reload")

    browser.close()

out = {
    "label": LABEL,
    "url": URL,
    "results": results,
    "console_errors": [c for c in console if c["type"] == "error"],
    "console_warnings": [c for c in console if c["type"] == "warning"],
    "console_all_count": len(console),
    "page_errors": page_errors,
    "failed_requests": failed,
    "bad_responses": sorted(set(bad_responses)),
}
print(json.dumps(out, indent=2, default=str))
