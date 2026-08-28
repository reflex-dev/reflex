"""Playwright driver for the local-component example app.

Usage: python drive_local_component.py <frontend_url> <outdir>

Flows exercised:
 1. Initial render: heading + local JSX Hello component says "Hello world!"
 2. Click greeting -> popover opens -> type name -> Enter submits -> "Hello <name>!"
 3. Right-click greeting h1 -> console log "Yes we pass events through" + caps toggle
 4. Color mode toggle changes the Hello div background color (papayawhip <-> rebeccapurple)
 5. "Scroll to Greeting" button scrolls back up
Captures console messages, failed requests/responses, screenshots.
Writes JSON results to <outdir>/result.json; exit 0 iff all steps pass.
"""

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = sys.argv[1]
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)

console_msgs: list[dict] = []
failed_requests: list[str] = []
bad_responses: list[str] = []
results: list[dict] = []


def step(name: str, ok: bool, detail: str = ""):
    results.append({"name": name, "ok": bool(ok), "detail": detail})
    print(f"{'PASS' if ok else 'FAIL'}: {name} {detail}")


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.on(
        "console",
        lambda m: console_msgs.append({"type": m.type, "text": m.text}),
    )
    page.on("requestfailed", lambda r: failed_requests.append(f"{r.method} {r.url} -> {r.failure}"))
    page.on(
        "response",
        lambda r: bad_responses.append(f"{r.status} {r.url}") if r.status >= 400 else None,
    )

    page.goto(URL, wait_until="load", timeout=60000)

    # 1. Initial render
    try:
        page.wait_for_selector("text=Local Component Example", timeout=30000)
        greeting = page.locator("#greeting h1")
        greeting.wait_for(state="visible", timeout=15000)
        txt = greeting.inner_text()
        step("initial_render", txt == "Hello world!", f"greeting={txt!r}")
    except Exception as e:
        step("initial_render", False, repr(e))
    page.screenshot(path=str(OUT / "01_initial.png"), full_page=False)

    # 2. Click greeting -> popover -> type name -> Enter
    try:
        page.locator("#greeting").click()
        inp = page.locator("input[name='who']")
        inp.wait_for(state="visible", timeout=10000)
        page.screenshot(path=str(OUT / "02_popover_open.png"))
        inp.fill("Reflex")
        # on_change fires per change; greeting should live-update while typing
        time.sleep(1.0)
        live = page.locator("#greeting h1").inner_text()
        inp.press("Enter")
        page.wait_for_selector("input[name='who']", state="hidden", timeout=10000)
        time.sleep(0.5)
        txt = page.locator("#greeting h1").inner_text()
        step(
            "popover_edit_submit",
            txt == "Hello Reflex!",
            f"live_while_typing={live!r} after_submit={txt!r}",
        )
    except Exception as e:
        step("popover_edit_submit", False, repr(e))
    page.screenshot(path=str(OUT / "03_after_submit.png"))

    # 3. Right-click toggles caps + console log passthrough
    try:
        n_before = len([m for m in console_msgs if "Yes we pass events through" in m["text"]])
        page.locator("#greeting h1").click(button="right")
        time.sleep(1.0)
        txt = page.locator("#greeting h1").inner_text()
        n_after = len([m for m in console_msgs if "Yes we pass events through" in m["text"]])
        step(
            "context_menu_caps",
            txt == "HELLO REFLEX!" and n_after == n_before + 1,
            f"text={txt!r} console_log_count {n_before}->{n_after}",
        )
        # toggle back
        page.locator("#greeting h1").click(button="right")
        time.sleep(0.5)
    except Exception as e:
        step("context_menu_caps", False, repr(e))
    page.screenshot(path=str(OUT / "04_after_rightclick.png"))

    # 4. Color mode toggle changes background color
    try:
        bg_light = page.locator("#greeting").evaluate(
            "el => getComputedStyle(el).backgroundColor"
        )
        page.locator("button", has=page.locator("svg")).first.click()  # color mode button (top-right)
        time.sleep(1.0)
        bg_dark = page.locator("#greeting").evaluate(
            "el => getComputedStyle(el).backgroundColor"
        )
        # papayawhip = rgb(255, 239, 213); rebeccapurple = rgb(102, 51, 153)
        ok = {bg_light, bg_dark} == {"rgb(255, 239, 213)", "rgb(102, 51, 153)"}
        step("color_mode_bg", ok, f"light={bg_light} dark={bg_dark}")
        page.screenshot(path=str(OUT / "05_dark_mode.png"))
        page.locator("button", has=page.locator("svg")).first.click()  # back to light
        time.sleep(0.5)
    except Exception as e:
        step("color_mode_bg", False, repr(e))

    # 5. Scroll to greeting
    try:
        page.locator("text=Scroll to Greeting").scroll_into_view_if_needed()
        time.sleep(0.3)
        y_before = page.evaluate("window.scrollY")
        page.locator("text=Scroll to Greeting").click()
        time.sleep(1.5)
        y_after = page.evaluate("window.scrollY")
        step("scroll_to", y_before > 200 and y_after < y_before, f"scrollY {y_before} -> {y_after}")
    except Exception as e:
        step("scroll_to", False, repr(e))
    page.screenshot(path=str(OUT / "06_after_scroll.png"))

    time.sleep(1.0)
    ctx.close()
    browser.close()

BENIGN = ("HydrateFallback", "[vite] connecting", "[vite] connected", "React DevTools")
noteworthy = [
    m
    for m in console_msgs
    if m["type"] in ("error", "warning")
    and not any(b in m["text"] for b in BENIGN)
]
out = {
    "url": URL,
    "steps": results,
    "console_all": console_msgs,
    "console_noteworthy": noteworthy,
    "failed_requests": failed_requests,
    "bad_responses": bad_responses,
}
(OUT / "result.json").write_text(json.dumps(out, indent=2))
print("noteworthy console:", json.dumps(noteworthy, indent=2))
print("failed_requests:", failed_requests)
print("bad_responses:", bad_responses)
sys.exit(0 if all(r["ok"] for r in results) else 1)
